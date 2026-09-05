#!/usr/bin/env python3
"""Build or verify a private-source Lua 5.1.5 filtered assignment reference experiment."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document
from src.observatory.lua51_filtered_assignment_reference import (
    AssignmentReferenceError,
    build_reference,
    validate_reference,
    validate_structure,
    encode_reference,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify", "verify-structure"):
        p = sub.add_parser(name)
        if name != "verify-structure":
            p.add_argument("--archive", type=Path, required=True)
        if name != "build":
            p.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_reference(args.archive)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_reference(evidence).encode():
                raise AssignmentReferenceError("noncanonical file encoding")
            result = (
                validate_structure(evidence)
                if args.command == "verify-structure"
                else validate_reference(args.archive, evidence)
            )
        sys.stdout.buffer.write(encode_reference(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
