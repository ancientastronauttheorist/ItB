#!/usr/bin/env python3
"""Replay ``fuzzy_detector.evaluate`` against recordings/failure_db.jsonl.

Validates that the detector handles every record in the historical
corpus without crashing, and reports what would have been soft-disabled
if Phase 1 had been live the whole time. Run whenever ``evaluate``
logic changes — this is the #P1-6 regression gate.

Per-run replay: entries are ordered by (run_id, mission, turn,
action_index) so frequency accumulation mirrors live ordering. Cross-run
counts do NOT accumulate — each run_id gets a fresh prior_events list,
matching live semantics (``failure_events_this_run`` resets per run).

Records written before the Phase 0 hook landed (pre-2026-04-17) have no
``fuzzy_signal`` field, so their ``weapon`` context is unknown and the
signature falls back to ``<category>||<sub_action>`` — still useful for
category/frequency breakdowns, just coarser.

Usage::

    python3 scripts/replay_fuzzy_detector.py
    python3 scripts/replay_fuzzy_detector.py --json > report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.solver import fuzzy_detector  # noqa: E402

FAILURE_DB = REPO / "recordings" / "failure_db.jsonl"


def _reconstruct_diff(record: dict) -> SimpleNamespace:
    diff_blob = record.get("diff") or {}
    return SimpleNamespace(
        unit_diffs=diff_blob.get("unit_diffs", []) or [],
        tile_diffs=diff_blob.get("tile_diffs", []) or [],
        scalar_diffs=diff_blob.get("scalar_diffs", []) or [],
    )


def _reconstruct_classification(record: dict) -> dict:
    """Minimal classification dict from a failure_db record.

    Pre-Phase-0 records only stored ``category`` + ``subcategory`` (not
    the full ``categories`` list). Close enough for the replay; Phase 0+
    records carry the whole thing via ``fuzzy_signal``.
    """
    stored = record.get("fuzzy_signal") or {}
    cat = record.get("category")
    return {
        "top_category": stored.get("top_category") or cat,
        "categories": stored.get("categories") or ([cat] if cat else []),
        "subcategory": stored.get("subcategory") or record.get("subcategory"),
        "model_gap": stored.get(
            "model_gap",
            (record.get("context") or {}).get("model_gap", False),
        ),
    }


def _reconstruct_context(record: dict) -> dict:
    stored = (record.get("fuzzy_signal") or {}).get("context") or {}
    return {
        "mech_uid": record.get("mech_uid") or stored.get("mech_uid"),
        "phase": record.get("sub_action") or stored.get("phase"),
        "sub_action": record.get("sub_action") or stored.get("sub_action"),
        "action_index": record.get("action_index") or stored.get("action_index"),
        "turn": record.get("turn") or stored.get("turn"),
        "weapon": stored.get("weapon"),
    }


def _sort_key(record: dict) -> tuple:
    return (
        record.get("run_id", ""),
        int(record.get("mission", 0) or 0),
        int(record.get("turn", 0) or 0),
        int(record.get("action_index", 0) or 0),
    )


def replay() -> dict:
    if not FAILURE_DB.is_file():
        return {"error": f"{FAILURE_DB} not found"}

    records: list[dict] = []
    for line in FAILURE_DB.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    per_sub = [r for r in records if r.get("trigger", "").startswith(
        "per_sub_action_desync_")]
    per_sub.sort(key=_sort_key)

    per_run_events: dict[str, list[dict]] = defaultdict(list)
    category_counts: Counter = Counter()
    tier_counts: Counter = Counter()
    soft_disable_triggers: list[dict] = []
    model_gap_count = 0
    crashes: list[str] = []

    for rec in per_sub:
        run_id = rec.get("run_id", "")
        diff_obj = _reconstruct_diff(rec)
        classification = _reconstruct_classification(rec)
        context = _reconstruct_context(rec)
        prior = per_run_events[run_id]
        try:
            signal = fuzzy_detector.evaluate(
                diff_obj, classification, context=context, prior_events=prior,
            )
        except Exception as e:  # noqa: BLE001 — report, don't abort
            crashes.append(f"{rec.get('id')}: {type(e).__name__}: {e}")
            continue

        per_run_events[run_id].append(signal)
        category_counts[signal.get("top_category") or "unknown"] += 1
        tier_counts[signal.get("proposed_tier")] += 1
        if signal.get("model_gap"):
            model_gap_count += 1
        if signal.get("proposed_tier") == 2:
            soft_disable_triggers.append({
                "id": rec.get("id"),
                "weapon": (context.get("weapon") or "?"),
                "signature": signal.get("signature"),
                "frequency": signal.get("frequency"),
                "confidence": signal.get("confidence"),
            })

    return {
        "total_records": len(records),
        "per_sub_action_records": len(per_sub),
        "runs_covered": len(per_run_events),
        "by_category": dict(category_counts.most_common()),
        "by_tier": {str(k): v for k, v in tier_counts.items()},
        "soft_disable_triggers": len(soft_disable_triggers),
        "soft_disable_unique_weapons": sorted({
            sd["weapon"] for sd in soft_disable_triggers
            if sd["weapon"] not in (None, "", "?")
        }),
        "model_gap_events": model_gap_count,
        "crashes": crashes,
        "soft_disable_examples": soft_disable_triggers[:10],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    report = replay()
    if "error" in report:
        print(report["error"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=False))
        return 0 if not report["crashes"] else 2

    print(f"Replayed {report['per_sub_action_records']} per-sub-action "
          f"records across {report['runs_covered']} run(s) "
          f"(total failure_db = {report['total_records']}).")
    print()
    print("By category:")
    for cat, n in report["by_category"].items():
        print(f"  {cat:<22} {n}")
    print()
    print("By proposed tier:")
    for tier, n in report["by_tier"].items():
        print(f"  tier {tier:<3} {n}")
    print()
    print(f"Model-gap events:           {report['model_gap_events']}")
    print(f"Would soft-disable (tier 2): {report['soft_disable_triggers']}")
    if report["soft_disable_unique_weapons"]:
        print(f"Weapons implicated: {', '.join(report['soft_disable_unique_weapons'])}")
    if report["soft_disable_examples"]:
        print()
        print("First soft-disable examples:")
        for ex in report["soft_disable_examples"]:
            print(f"  {ex['id']:<60} weapon={ex['weapon']} "
                  f"freq={ex['frequency']} conf={ex['confidence']:.2f}")
    if report["crashes"]:
        print()
        print(f"CRASHES: {len(report['crashes'])}")
        for msg in report["crashes"][:5]:
            print(f"  {msg}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
