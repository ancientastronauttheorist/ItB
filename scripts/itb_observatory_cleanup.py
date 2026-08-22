#!/usr/bin/env python3
"""Restore and clean an ITB Observatory campaign installation."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observatory.campaign_cleanup import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
