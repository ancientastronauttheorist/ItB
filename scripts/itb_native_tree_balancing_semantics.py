#!/usr/bin/env python3
"""Build or verify the independent synthetic balancing model; no PE required."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_tree_balancing_semantics import (
    BalancingError,
    SOURCE_PINS,
    build_semantics,
    encode_semantics,
    validate_semantics,
    validate_structure,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for source in SOURCE_PINS:
            item.add_argument("--" + source.replace("_", "-"), required=True, type=Path)
        if command != "build":
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        sources = {
            key: _read_json_object(getattr(args, key), key) for key in SOURCE_PINS
        }
        if args.command == "build":
            result = build_semantics(sources)
        else:
            evidence, raw = _read_json_document(args.evidence, "evidence")
            if raw != encode_semantics(evidence).encode("utf-8"):
                raise BalancingError("evidence is not deterministically encoded")
            result = (
                validate_structure
                if args.command == "verify-structure"
                else validate_semantics
            )(evidence, sources)
        sys.stdout.buffer.write(encode_semantics(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
