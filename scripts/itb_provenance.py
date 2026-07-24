#!/usr/bin/env python3
"""Validate an ITB mechanics provenance index against its exact inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from src.observatory.provenance import (  # noqa: E402
    ProvenanceError,
    audit_provenance_gaps,
    audit_provenance_sources,
    load_json_object,
    validate_provenance,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    audit_group = parser.add_mutually_exclusive_group()
    audit_group.add_argument(
        "--audit-sources",
        action="store_true",
        help="print a deterministic high-value Lua source-index audit",
    )
    audit_group.add_argument(
        "--audit-gaps",
        action="store_true",
        help="print a deterministic build-keyed queue of open mechanics gaps",
    )
    args = parser.parse_args(argv)
    try:
        provenance = load_json_object(args.provenance)
        inventory = load_json_object(args.inventory)
        if args.audit_sources:
            result = audit_provenance_sources(
                provenance,
                inventory,
                repo_root=args.repo_root,
            )
        elif args.audit_gaps:
            result = audit_provenance_gaps(
                provenance,
                inventory,
                repo_root=args.repo_root,
            )
        else:
            counts = validate_provenance(
                provenance,
                inventory,
                repo_root=args.repo_root,
            )
            result = {"status": "valid", "coverage": counts}
    except (OSError, UnicodeError, json.JSONDecodeError, ProvenanceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.audit_sources or args.audit_gaps else None,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
