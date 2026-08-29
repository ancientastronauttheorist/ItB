#!/usr/bin/env python3
"""Rebuild the derived native spawn-coordinate selector-state receipt."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.spawn_coordinate_state_replay import (  # noqa: E402
    build_spawn_coordinate_state_replay_receipt,
    canonical_json_bytes,
)


def main() -> int:
    receipt = build_spawn_coordinate_state_replay_receipt(ROOT)
    sys.stdout.buffer.write(canonical_json_bytes(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
