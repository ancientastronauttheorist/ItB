#!/usr/bin/env python3
"""Validate and summarize immutable Engine Observatory trace evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.trace_store import (  # noqa: E402
    TraceStoreError,
    build_identity_from_inventory,
    load_json_object,
    read_final_trace,
    summarize_trace,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a finalized Observatory trace against an exact trusted "
            "content inventory and capture identity."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "summary"):
        child = subparsers.add_parser(command)
        child.add_argument("trace", type=Path)
        child.add_argument(
            "--inventory",
            type=Path,
            required=True,
            help="trusted content-inventory JSON",
        )
        child.add_argument(
            "--capture-identity",
            type=Path,
            required=True,
            help="trusted capture_identity JSON object",
        )
        child.add_argument(
            "--trace-sha256",
            required=True,
            help="trusted SHA-256 of the finalized trace bytes",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inventory = load_json_object(args.inventory, "inventory")
        expected_build = build_identity_from_inventory(inventory)
        expected_capture = load_json_object(
            args.capture_identity,
            "capture identity",
        )
        trace_path = Path(os.path.abspath(args.trace.expanduser()))
        trace = read_final_trace(
            trace_path,
            expected_build_identity=expected_build,
            expected_capture_identity=expected_capture,
            expected_trace_sha256=args.trace_sha256,
            root=trace_path.parent,
        )
    except TraceStoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(
            "valid "
            f"capture={trace['capture_identity']['capture_id']} "
            f"checkpoint={trace['checkpoint']['seq']} "
            f"events={len(trace['events'])}"
        )
    else:
        print(
            json.dumps(
                summarize_trace(trace),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
