#!/usr/bin/env python3
"""Build or verify fallback global and stack stores; builds emit JSON to stdout."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
from scripts.itb_native_lua_direct_calls import _read_json_document, _read_json_object
from src.observatory.native_assertion_helper_failure_stores import (
    SOURCE_PINS,
    FailureStoreError,
    build_stores,
    validate_stores,
    validate_structure,
    encode_stores,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for source in SOURCE_PINS:
            item.add_argument("--" + source.replace("_", "-"), required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
        if command != "build":
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sources = {k: _read_json_object(getattr(args, k), k) for k in SOURCE_PINS}
        if args.command == "build":
            result = build_stores(args.executable, sources)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_stores(evidence).encode("utf-8"):
                raise FailureStoreError("evidence is not deterministically encoded")
            result = (
                validate_structure(evidence, sources)
                if args.command == "verify-structure"
                else validate_stores(args.executable, evidence, sources)
            )
        sys.stdout.buffer.write(encode_stores(result).encode("utf-8"))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
