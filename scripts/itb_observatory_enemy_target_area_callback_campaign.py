#!/usr/bin/env python3
"""Archive and seal the synthetic Firefly GetTargetArea campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.enemy_target_area_callback_campaign import (  # noqa: E402
    EnemyTargetAreaCallbackCampaignError,
    archive_enemy_target_area_callback_campaign,
    build_enemy_target_area_callback_campaign_receipt,
    publish_enemy_target_area_callback_campaign_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Archive accepted external outputs before building the receipt",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.source_root is not None:
            archive_enemy_target_area_callback_campaign(
                args.source_root,
                args.campaign_root,
            )
        receipt = build_enemy_target_area_callback_campaign_receipt(
            args.campaign_root,
            repository_root=args.repository_root,
        )
        path, digest = publish_enemy_target_area_callback_campaign_receipt(
            receipt,
            args.output,
        )
    except (
        EnemyTargetAreaCallbackCampaignError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "campaign_root": str(args.campaign_root.resolve()),
                "receipt": str(path),
                "sha256": digest,
                "pair_count": receipt["campaign"]["pair_count"],
                "event_counts": receipt["results"]["exact_event_counts"],
                "classification": receipt["results"]["classification"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
