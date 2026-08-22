#!/usr/bin/env python3
"""Validate and seal the matched natural callback campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.callback_campaign_receipt import (  # noqa: E402
    CallbackCampaignReceiptError,
    build_callback_campaign_receipt,
    publish_callback_campaign_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.output is None:
            value = build_callback_campaign_receipt(
                args.campaign_root,
                repository_root=args.repository_root,
            )
            print(json.dumps(value, indent=2, sort_keys=True))
        else:
            path, digest = publish_callback_campaign_receipt(
                args.campaign_root,
                repository_root=args.repository_root,
                output=args.output,
            )
            print(json.dumps({"path": str(path), "sha256": digest}, indent=2))
        return 0
    except (CallbackCampaignReceiptError, OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
