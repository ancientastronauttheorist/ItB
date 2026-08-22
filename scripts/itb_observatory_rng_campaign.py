#!/usr/bin/env python3
"""Validate and immutably seal the archived seeded RNG campaign."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.rng_campaign_receipt import (  # noqa: E402
    RngCampaignReceiptError,
    publish_seeded_rng_campaign_receipt,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output, digest = publish_seeded_rng_campaign_receipt(
            args.campaign_root,
            repository_root=args.repository_root,
            output=args.output,
        )
    except RngCampaignReceiptError as exc:
        parser.error(str(exc))
    print(f"sealed {output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
