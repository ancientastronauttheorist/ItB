#!/usr/bin/env python3
"""Build or verify the second child of the assertion direct-callee pair."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts import (  # noqa: E402
    itb_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary as _writer,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary import (  # noqa: E402
    ANALYSIS_KIND,
    NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError as Error,
    build_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary as build,
    encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary as encode,
    validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary as validate,
    validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_structure as validate_structure,
)

_read_json_document = _writer._read_json_document
_read_json_object = _writer._read_json_object


def _write_immutably(output: Path, rendered: str, value: dict[str, Any]) -> None:
    original = _writer.ANALYSIS_KIND
    try:
        _writer.ANALYSIS_KIND = ANALYSIS_KIND
        _writer._write_immutably(output, rendered, value)
    except Exception as exc:
        raise Error(str(exc)) from exc
    finally:
        _writer.ANALYSIS_KIND = original


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify", "verify-structure"):
        item = commands.add_parser(command)
        for name in (
            "direct-callee-pair-static-boundary",
            "direct-calls",
            "program-facts",
        ):
            item.add_argument("--" + name, required=True, type=Path)
        if command != "verify-structure":
            item.add_argument("--executable", required=True, type=Path)
            item.add_argument("--inventory", required=True, type=Path)
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        get = lambda name: _read_json_object(
            getattr(args, name.replace("-", "_")), name
        )
        predecessor, direct, facts = (
            get(name)
            for name in (
                "direct-callee-pair-static-boundary",
                "direct-calls",
                "program-facts",
            )
        )
        common = (predecessor, direct, facts)
        if args.command == "build":
            result = build(args.executable, *common, inventory=get("inventory"))
            rendered = encode(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode(evidence).encode("utf-8"):
                raise Error("evidence is not deterministically encoded")
            result = (
                validate(args.executable, evidence, *common, inventory=get("inventory"))
                if args.command == "verify"
                else validate_structure(evidence, *common)
            )
            sys.stdout.write(encode(result))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
