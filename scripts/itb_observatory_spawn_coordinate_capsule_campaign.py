#!/usr/bin/env python3
"""Validate and publish a selector-entry Board/RNG capsule campaign receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.spawn_coordinate_capsule_campaign import (  # noqa: E402
    SpawnCoordinateCapsuleCampaignError,
    build_spawn_coordinate_capsule_campaign_receipt,
    publish_spawn_coordinate_capsule_campaign_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        receipt = build_spawn_coordinate_capsule_campaign_receipt(
            args.campaign_root,
            repository_root=args.repository_root,
        )
        if args.output is None:
            print(json.dumps(receipt, indent=2, sort_keys=True))
        else:
            path, digest = publish_spawn_coordinate_capsule_campaign_receipt(
                receipt, args.output
            )
            print(f"receipt={path} sha256={digest}")
        return 0
    except (OSError, SpawnCoordinateCapsuleCampaignError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
