"""Tests for the shared failure-db cutoff helpers in src/solver/analysis.py.

The cutoff config (``data/mining_cutoff.json``) is consumed by both
the override miner and the tuner's failure corpus. These tests pin
the semantics that both callers rely on — in particular:

- Missing/broken config → no filter (never silently crash a run).
- Unset caller arg → load config from disk.
- Explicit ``None`` → disable filter entirely.
- Explicit ISO string → use as-is.
- Rows without a ``timestamp`` field pass through (legacy rows
  predate the stamp; conservative behavior beats silent drop).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.solver import analysis as an


def test_normalize_ts_strips_tz_offset():
    assert an._normalize_ts("2026-04-13T21:31:37-05:00") == "2026-04-13T21:31:37"
    assert an._normalize_ts("2026-04-13T21:31:37+00:00") == "2026-04-13T21:31:37"
    assert an._normalize_ts("2026-04-13T21:31:37Z") == "2026-04-13T21:31:37"
    assert an._normalize_ts("2026-04-13T21:31:37") == "2026-04-13T21:31:37"
    # Date-portion hyphen must survive.
    assert an._normalize_ts("2026-04-13") == "2026-04-13"


def test_load_failure_cutoff_missing_is_none(tmp_path: Path):
    assert an.load_failure_cutoff(tmp_path / "nope.json") is None


def test_load_failure_cutoff_malformed_is_none(tmp_path: Path):
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    assert an.load_failure_cutoff(p) is None

    p.write_text(json.dumps([1, 2]))  # wrong top-level type
    assert an.load_failure_cutoff(p) is None

    p.write_text(json.dumps({"note": "no timestamp key here"}))
    assert an.load_failure_cutoff(p) is None


def test_load_failure_cutoff_reads_value(tmp_path: Path):
    p = tmp_path / "cutoff.json"
    p.write_text(json.dumps({"min_timestamp": "2026-04-13T21:31:37"}))
    assert an.load_failure_cutoff(p) == "2026-04-13T21:31:37"


def _rows() -> list[dict]:
    return [
        {"id": "a", "timestamp": "2026-04-10T10:00:00"},  # pre
        {"id": "b", "timestamp": "2026-04-11T10:00:00"},  # pre
        {"id": "c", "timestamp": "2026-04-14T10:00:00"},  # post
        {"id": "d", "timestamp": "2026-04-15T10:00:00"},  # post
    ]


def test_filter_by_timestamp_explicit_cutoff():
    out = an.filter_by_timestamp(_rows(), "2026-04-13T21:31:37")
    assert [r["id"] for r in out] == ["c", "d"]


def test_filter_by_timestamp_none_disables_filter():
    """Explicit ``None`` must keep every row — the historical-audit mode.
    An empty string likewise disables (falsy), since both config-missing
    and caller-opt-out converge here."""
    out = an.filter_by_timestamp(_rows(), None)
    assert [r["id"] for r in out] == ["a", "b", "c", "d"]


def test_filter_by_timestamp_unset_loads_config(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "cutoff.json"
    cfg.write_text(json.dumps({"min_timestamp": "2026-04-13T21:31:37"}))
    monkeypatch.setattr(an, "_DEFAULT_CUTOFF_PATH", cfg)
    out = an.filter_by_timestamp(_rows())
    assert [r["id"] for r in out] == ["c", "d"]


def test_filter_by_timestamp_unset_no_config_passes_through(
    tmp_path: Path, monkeypatch,
):
    """No config file → no cutoff. A fresh clone with nothing set must
    behave identically to pre-cutoff tuner runs, not silently drop
    every row."""
    monkeypatch.setattr(an, "_DEFAULT_CUTOFF_PATH", tmp_path / "missing.json")
    out = an.filter_by_timestamp(_rows())
    assert [r["id"] for r in out] == ["a", "b", "c", "d"]


def test_filter_by_timestamp_preserves_legacy_rows():
    """Legacy rows without a ``timestamp`` field survive the filter —
    they predate the stamp convention, and silently dropping them would
    erase the oldest observations (the ones the tuner most needs to
    know still reproduce)."""
    rows = [
        {"id": "legacy"},  # no timestamp
        {"id": "pre", "timestamp": "2026-04-10T10:00:00"},
        {"id": "post", "timestamp": "2026-04-14T10:00:00"},
    ]
    out = an.filter_by_timestamp(rows, "2026-04-13T21:31:37")
    assert {r["id"] for r in out} == {"legacy", "post"}


def test_filter_by_timestamp_tz_and_naive_compare_equally():
    """Cutoff may be config-authored with a TZ offset; rows are tz-naive.
    Both sides must compare as naive-local after normalization."""
    rows = [
        {"id": "pre", "timestamp": "2026-04-13T21:31:36"},
        {"id": "at", "timestamp": "2026-04-13T21:31:37"},
        {"id": "post", "timestamp": "2026-04-13T21:31:38"},
    ]
    out = an.filter_by_timestamp(rows, "2026-04-13T21:31:37-05:00")
    assert {r["id"] for r in out} == {"at", "post"}
