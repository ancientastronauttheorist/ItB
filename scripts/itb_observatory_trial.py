#!/usr/bin/env python3
"""Validate and compare inert Engine Observatory matched-trial receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.matched_trial import (  # noqa: E402
    MatchedTrialError,
    compare_matched_receipts,
    load_json_contract,
    validate_suite_contract,
    validate_trial_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    suite = subparsers.add_parser("validate-suite", help="validate one suite contract")
    suite.add_argument("suite", type=Path)
    receipt = subparsers.add_parser("validate-receipt", help="validate one trial receipt")
    receipt.add_argument("receipt", type=Path)
    receipt.add_argument("--suite", type=Path, required=True)
    compare = subparsers.add_parser("compare", help="compare control and exact-hook receipts")
    compare.add_argument("--suite", type=Path, required=True)
    compare.add_argument("--control", type=Path, required=True)
    compare.add_argument("--exact-hook", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-suite":
            suite = validate_suite_contract(load_json_contract(args.suite, "suite"))
            print(f"valid suite={suite['suite_id']} pair_nonce={suite['pair_nonce']}")
            return 0
        suite = validate_suite_contract(load_json_contract(args.suite, "suite"))
        if args.command == "validate-receipt":
            receipt = validate_trial_receipt(
                load_json_contract(args.receipt, "receipt"), expected_suite=suite
            )
            print(f"valid condition={receipt['condition']} suite={suite['suite_id']}")
            return 0
        comparison = compare_matched_receipts(
            load_json_contract(args.control, "control receipt"),
            load_json_contract(args.exact_hook, "exact-hook receipt"),
            expected_suite=suite,
        )
        print(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except MatchedTrialError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
