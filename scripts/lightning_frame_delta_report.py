#!/usr/bin/env python3
"""Generate Lightning War screenshot delta review artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.loop.lightning_telemetry import generate_frame_delta_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate frame_deltas.jsonl, interesting_frames.md, and contact_sheet.png",
    )
    parser.add_argument("run_dir", help="Recording run directory, e.g. recordings/<run_id>")
    args = parser.parse_args()
    result = generate_frame_delta_report(Path(args.run_dir))
    print(result)
    return 0 if result.get("status") in {"OK", "SKIPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
