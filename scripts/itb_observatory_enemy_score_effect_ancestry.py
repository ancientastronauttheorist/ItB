#!/usr/bin/env python3
"""Build or verify the exact shipped enemy score/effect ancestry map."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CALLBACK_ROOT = (ROOT / "data" / "observatory" / "callbacks").resolve()

from src.observatory.enemy_score_effect_ancestry import (  # noqa: E402
    EnemyScoreEffectAncestryError,
    build_enemy_score_effect_ancestry,
    encode_enemy_score_effect_ancestry,
    validate_enemy_score_effect_ancestry,
)


def _reject_constant(value: str) -> None:
    raise EnemyScoreEffectAncestryError(f"invalid JSON constant: {value}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnemyScoreEffectAncestryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise EnemyScoreEffectAncestryError(
            f"{label} is not a regular non-symlink file"
        )
    if path.stat().st_size > 16 * 1024 * 1024:
        raise EnemyScoreEffectAncestryError(f"{label} exceeds size limit")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicates,
    )
    if not isinstance(value, dict):
        raise EnemyScoreEffectAncestryError(f"{label} must contain an object")
    return value


def _write_create_only(path: Path, encoded: str) -> None:
    if path.exists() or path.is_symlink():
        raise EnemyScoreEffectAncestryError(
            "output already exists; publication is create-only"
        )
    parent = path.parent.resolve()
    if (
        parent != CALLBACK_ROOT
        or path.parent.is_symlink()
        or not parent.is_dir()
        or not path.name.endswith(".json")
    ):
        raise EnemyScoreEffectAncestryError(
            "file output is restricted to data/observatory/callbacks JSON artifacts"
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


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--content-root", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--callback-index", required=True, type=Path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    _common(build)
    build.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify")
    _common(verify)
    verify.add_argument("--ancestry-map", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inventory = _read_json(args.inventory, "content inventory")
        callback_index = _read_json(args.callback_index, "callback index")
        if args.command == "build":
            value = build_enemy_score_effect_ancestry(
                args.content_root,
                inventory,
                callback_index,
            )
            encoded = encode_enemy_score_effect_ancestry(value)
            if args.output is None:
                sys.stdout.write(encoded)
            else:
                _write_create_only(args.output, encoded)
        else:
            result = validate_enemy_score_effect_ancestry(
                args.content_root,
                inventory,
                callback_index,
                _read_json(args.ancestry_map, "enemy score/effect ancestry map"),
            )
            sys.stdout.write(encode_enemy_score_effect_ancestry(result))
        return 0
    except (
        EnemyScoreEffectAncestryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
