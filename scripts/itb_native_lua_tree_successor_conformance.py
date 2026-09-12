#!/usr/bin/env python3
"""Build or verify native successor evidence against its sealed semantics."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_lua_tree_successor_conformance import (
    ConformanceError,
    build_conformance,
    validate_conformance,
    validate_structure,
    encode_conformance,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        item.add_argument("--semantics", required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
        if command != "build":
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        sources = {"semantics": _read_json_object(args.semantics, "semantics")}
        if args.command == "build":
            result = build_conformance(args.executable, sources)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_conformance(evidence).encode("utf-8"):
                raise ConformanceError("evidence is not deterministically encoded")
            result = (
                validate_structure(evidence, sources)
                if args.command == "verify-structure"
                else validate_conformance(args.executable, evidence, sources)
            )
        sys.stdout.buffer.write(encode_conformance(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
