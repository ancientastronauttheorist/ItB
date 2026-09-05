#!/usr/bin/env python3
"""Build or verify finite Lua helper reference contract projections without execution."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_lua_helper_reference_contracts import (
    SOURCE_PINS,
    ContractError,
    build_contracts,
    validate_structure,
    encode_contracts,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify-structure"):
        item = commands.add_parser(command)
        for source in SOURCE_PINS:
            item.add_argument("--" + source.replace("_", "-"), required=True, type=Path)
        if command != "build":
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        sources = {k: _read_json_object(getattr(args, k), k) for k in SOURCE_PINS}
        if args.command == "build":
            result = build_contracts(sources)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_contracts(evidence).encode("utf-8"):
                raise ContractError("evidence is not deterministically encoded")
            result = validate_structure(evidence, sources)
        sys.stdout.buffer.write(encode_contracts(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
