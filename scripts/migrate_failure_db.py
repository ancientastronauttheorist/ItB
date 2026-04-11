#!/usr/bin/env python3
"""Backfill the failure database with category + auto_fixable_by_tuning fields.

Idempotent. Re-running on a fully migrated database is a no-op. Adds two
fields to each record that lacks them:

  category:               Phase 2 verify-style category derived from the
                          trigger name (grid_power, damage_amount, death,
                          search_exhaustion, strategic_decline, click_miss,
                          unknown).

  auto_fixable_by_tuning: bool — whether this record is plausibly fixable
                          by re-tuning solver weights. Per-trigger lookup
                          fallback only — the counterfactual mech-position
                          check requires a live Board, which the historical
                          records don't carry.

Atomic write: writes to ``failure_db.jsonl.tmp`` then ``os.replace``.

Usage:
    python3 scripts/migrate_failure_db.py
    python3 scripts/migrate_failure_db.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.solver.analysis import (  # noqa: E402
    _trigger_category,
    is_auto_fixable_by_tuning,
)

FAILURE_DB = ROOT / "recordings" / "failure_db.jsonl"


def migrate(dry_run: bool = False) -> dict:
    if not FAILURE_DB.exists():
        return {"status": "no_db", "path": str(FAILURE_DB)}

    records = []
    with open(FAILURE_DB) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  WARN: skipping malformed line: {e}")
                continue

    total = len(records)
    backfilled_category = 0
    backfilled_fixable = 0
    already_complete = 0

    for r in records:
        had_category = "category" in r
        had_fixable = "auto_fixable_by_tuning" in r

        if had_category and had_fixable:
            already_complete += 1
            continue

        if not had_category:
            r["category"] = _trigger_category(r.get("trigger", ""))
            backfilled_category += 1

        if not had_fixable:
            # Counterfactual path is unavailable for legacy records (no
            # board in scope) — fall back to the per-trigger lookup.
            r["auto_fixable_by_tuning"] = is_auto_fixable_by_tuning(r, board=None)
            backfilled_fixable += 1

    summary = {
        "total": total,
        "already_complete": already_complete,
        "backfilled_category": backfilled_category,
        "backfilled_fixable": backfilled_fixable,
        "dry_run": dry_run,
    }

    if dry_run:
        print(f"DRY RUN — would migrate {backfilled_category}/{total} records")
        return summary

    if backfilled_category == 0 and backfilled_fixable == 0:
        print(f"No records needed migration (all {total} already have both fields)")
        return summary

    tmp_path = FAILURE_DB.with_suffix(".jsonl.tmp")
    with open(tmp_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp_path), str(FAILURE_DB))

    print(f"Migrated {backfilled_category}/{total} records:")
    print(f"  category backfilled:    {backfilled_category}")
    print(f"  fixable flag backfilled: {backfilled_fixable}")
    print(f"  already complete:        {already_complete}")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing")
    args = parser.parse_args()
    summary = migrate(dry_run=args.dry_run)
    print()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
