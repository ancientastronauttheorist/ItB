#!/usr/bin/env python3
"""Verify reviewed native-boundary evidence against one exact ITB PE."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.pe_boundary_map import (  # noqa: E402
    PEBoundaryError,
    encode_boundary_verification,
    validate_pe_boundary_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    return parser


def _reject_json_constant(value: str) -> None:
    raise PEBoundaryError(f"invalid JSON constant: {value}")


def _read_json_object(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PEBoundaryError(f"{label} is not a regular non-symlink file")
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_json_constant,
    )
    if not isinstance(value, dict):
        raise PEBoundaryError(f"{label} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json_object(args.inventory, "inventory")
        evidence = _read_json_object(args.evidence, "evidence")
        result = validate_pe_boundary_map(
            args.executable,
            evidence,
            inventory=inventory,
        )
        sys.stdout.write(encode_boundary_verification(result))
        return 0
    except (
        PEBoundaryError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
