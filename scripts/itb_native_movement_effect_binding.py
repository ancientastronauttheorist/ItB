#!/usr/bin/env python3
"""Build or verify exact named movement-method builder source joins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_movement_effect_binding import (
    build_binding,
    validate_binding,
    validate_structure,
    encode_binding,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        item.add_argument("--program-facts", required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
        if command != "build":
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        sources = dict(
            program_facts=_read_json_object(args.program_facts, "program facts")
        )
        if args.command == "build":
            result = build_binding(args.executable, sources)
        else:
            evidence, raw = _read_json_document(args.evidence, "evidence")
            if raw != encode_binding(evidence).encode("utf-8"):
                raise ValueError("evidence is not deterministically encoded")
            result = (
                validate_structure(evidence, sources)
                if args.command == "verify-structure"
                else validate_binding(args.executable, evidence, sources)
            )
        sys.stdout.buffer.write(encode_binding(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
