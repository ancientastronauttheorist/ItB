#!/usr/bin/env python3
"""Build or verify the bounded exact x86 integrated vector deallocation replay."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_vector_deallocation_conformance_joined import (
    ConformanceError,
    build_conformance,
    validate_conformance,
    validate_structure,
    encode_conformance,
)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("build", "verify", "verify-structure"):
        s = sub.add_parser(name)
        s.add_argument("--composition", type=Path, required=True)
        if name != "verify-structure":
            s.add_argument("--executable", type=Path, required=True)
        if name != "build":
            s.add_argument("--evidence", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        composition = _read_json_object(args.composition, "composition")
        if args.command == "build":
            result = build_conformance(args.executable, composition)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_conformance(evidence).encode():
                raise ConformanceError("noncanonical encoding")
            result = (
                validate_structure(evidence, composition)
                if args.command == "verify-structure"
                else validate_conformance(args.executable, evidence, composition)
            )
        sys.stdout.buffer.write(encode_conformance(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
