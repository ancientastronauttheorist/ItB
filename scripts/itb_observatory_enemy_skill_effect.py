#!/usr/bin/env python3
"""Build, verify, or replay the exact native SkillEffect boundary."""

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
    "enemy_skill_effect_boundary.json"
)

from src.observatory.enemy_skill_effect_boundary import (  # noqa: E402
    EnemySkillEffectBoundaryError,
    build_enemy_skill_effect_boundary_map,
    encode_enemy_skill_effect_boundary_map,
    replay_enemy_skill_effect_boundary,
    validate_enemy_skill_effect_boundary_map,
    validate_enemy_skill_effect_boundary_map_binding,
)


def _reject_constant(value: str) -> None:
    raise EnemySkillEffectBoundaryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnemySkillEffectBoundaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EnemySkillEffectBoundaryError(
            f"{label} is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemySkillEffectBoundaryError(f"{label} exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise EnemySkillEffectBoundaryError(f"{label} must contain an object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise EnemySkillEffectBoundaryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != NATIVE_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise EnemySkillEffectBoundaryError(
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
            value = build_enemy_skill_effect_boundary_map(args.executable)
            encoded = encode_enemy_skill_effect_boundary_map(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        elif args.command == "verify":
            result = validate_enemy_skill_effect_boundary_map(
                args.executable,
                _read_json(args.boundary_map, "SkillEffect boundary map"),
            )
            sys.stdout.write(encode_enemy_skill_effect_boundary_map(result))
        else:
            validate_enemy_skill_effect_boundary_map_binding(
                _read_json(args.boundary_map, "SkillEffect boundary map")
            )
            payload = _read_json(args.payload, "SkillEffect replay payload")
            expected_fields = {
                "cached_target_points",
                "selected_target",
                "origin",
                "two_click",
                "second_target",
                "cached_effect",
                "get_skill_effect",
                "get_final_effect",
                "explosion",
                "skill_source_tag",
                "owner_id",
                "skill_id",
                "skill_key",
                "friendly_fire_passives",
                "friendly_fire_owner_matches_team6",
                "friendly_fire_target_points",
                "owner_boosted",
            }
            if set(payload) != expected_fields:
                raise EnemySkillEffectBoundaryError(
                    "SkillEffect replay payload fields differ from the exact schema"
                )
            result = replay_enemy_skill_effect_boundary(**payload)
            sys.stdout.write(encode_enemy_skill_effect_boundary_map(result))
        return 0
    except (
        EnemySkillEffectBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
