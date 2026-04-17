"""Phase 0 self-healing loop instrumentation tests.

Covers the four pieces that must exist before Phase 1 can be built on top:

1. ``RunSession.failure_events_this_run`` round-trips through the session
   serializer.
2. ``src.solver.fuzzy_detector.evaluate`` returns the agreed-upon dict
   shape so the Phase 1 detector has a stable input contract.
3. ``src.solver.unknown_detector.detect_unknowns`` flags pawn types and
   terrain ids that aren't in ``data/known_types.json``.
4. ``src.solver.analysis.append_to_failure_db`` passes ``fuzzy_signal``
   through to the on-disk JSONL record (backward-compatible: readers
   that don't know about the field still work because optional fields
   are accessed with ``.get()``).

All tests run without a live game — they exercise Python-only glue.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.loop.session import RunSession
from src.solver import fuzzy_detector, unknown_detector
from src.solver.verify import DiffResult
from src.solver import analysis


# ── #P0-1 round-trip ─────────────────────────────────────────────────────────


def test_failure_events_this_run_round_trips():
    s = RunSession(run_id="t")
    s.failure_events_this_run.append({"hello": "world", "n": 1})
    d = s.to_dict()
    assert d["failure_events_this_run"] == [{"hello": "world", "n": 1}]
    s2 = RunSession.from_dict(d)
    assert s2.failure_events_this_run == [{"hello": "world", "n": 1}]


def test_failure_events_default_empty_on_legacy_session_dict():
    # A dict written before Phase 0 existed (no key) must still load.
    legacy = {"run_id": "old", "squad": "Rift"}
    s = RunSession.from_dict(legacy)
    assert s.failure_events_this_run == []


# ── #P0-2 stub contract ──────────────────────────────────────────────────────


def test_fuzzy_detector_stub_shape():
    diff = DiffResult()  # empty; stub doesn't read it
    classification = {
        "top_category": "damage_amount",
        "categories": ["damage_amount"],
        "subcategory": None,
        "model_gap": False,
    }
    ctx = {"mech_uid": 7, "phase": "attack", "action_index": 2, "turn": 3}
    sig = fuzzy_detector.evaluate(diff, classification, context=ctx)
    assert sig["version"] == 0
    assert sig["top_category"] == "damage_amount"
    assert sig["categories"] == ["damage_amount"]
    assert sig["model_gap"] is False
    assert sig["context"] == ctx


def test_fuzzy_detector_json_serializable():
    # Must be JSON-safe so it can land in session state + failure_db.jsonl.
    classification = {"top_category": "push_dir", "categories": ["push_dir"],
                      "subcategory": None, "model_gap": False}
    sig = fuzzy_detector.evaluate(DiffResult(), classification, context={})
    json.dumps(sig)  # must not raise


# ── #P0-5 novelty detection ──────────────────────────────────────────────────


def _fake_board(unit_types: list[str], terrain_ids: list[str]):
    """Minimal board duck-type for detect_unknowns.

    ``tiles`` is an 8×8 grid; only tile [0][0..N-1] carries the supplied
    terrain ids, everything else is "ground" (which is always known).
    """
    units = [SimpleNamespace(type=t) for t in unit_types]
    tiles = [[SimpleNamespace(terrain="ground") for _ in range(8)] for _ in range(8)]
    for i, tid in enumerate(terrain_ids):
        tiles[0][i].terrain = tid
    return SimpleNamespace(units=units, tiles=tiles)


def test_detect_unknowns_known_units_empty():
    unknown_detector.reset_cache()
    board = _fake_board(["Firefly1", "Scorpion1"], ["ground", "water"])
    r = unknown_detector.detect_unknowns(board)
    assert r == {"types": [], "terrain_ids": []}


def test_detect_unknowns_flags_novel_unit():
    unknown_detector.reset_cache()
    board = _fake_board(["Wumpus_Alpha", "Scorpion1"], [])
    r = unknown_detector.detect_unknowns(board)
    assert "Wumpus_Alpha" in r["types"]
    assert r["terrain_ids"] == []


def test_detect_unknowns_flags_novel_terrain():
    unknown_detector.reset_cache()
    board = _fake_board([], ["quicksand"])
    r = unknown_detector.detect_unknowns(board)
    assert "quicksand" in r["terrain_ids"]


# ── #P0-3 fuzzy_signal survives the failure_db round-trip ────────────────────


def test_fuzzy_signal_written_to_failure_db(monkeypatch, tmp_path):
    db_path = tmp_path / "failure_db.jsonl"
    monkeypatch.setattr(analysis, "FAILURE_DB_PATH", db_path)

    trigger = {
        "trigger": "per_sub_action_desync_attack",
        "tier": 2,
        "severity": "medium",
        "details": "test",
        "action_index": 0,
        "mech_uid": 3,
        "category": "damage_amount",
        "subcategory": None,
        "diff": {"unit_diffs": [], "tile_diffs": [], "scalar_diffs": [], "total_count": 0},
        "fuzzy_signal": {
            "version": 0,
            "top_category": "damage_amount",
            "categories": ["damage_amount"],
            "subcategory": None,
            "model_gap": False,
            "context": {"mech_uid": 3, "phase": "attack"},
        },
    }
    count = analysis.append_to_failure_db(
        [trigger], run_id="tr", mission_index=0, turn=1,
        context={"squad": "Rift", "island": "", "model_gap": False,
                 "weight_version": "v?", "solver_version": "v?", "tags": []},
    )
    assert count == 1

    # Round-trip: the written record carries fuzzy_signal verbatim.
    line = db_path.read_text().strip()
    rec = json.loads(line)
    assert "fuzzy_signal" in rec
    assert rec["fuzzy_signal"]["top_category"] == "damage_amount"
    assert rec["fuzzy_signal"]["context"]["phase"] == "attack"


def test_failure_db_reader_tolerates_missing_fuzzy_signal(monkeypatch, tmp_path):
    """Backward-compat check: trigger without fuzzy_signal still writes
    cleanly, and existing readers that ``.get("fuzzy_signal")`` see None."""
    db_path = tmp_path / "failure_db.jsonl"
    monkeypatch.setattr(analysis, "FAILURE_DB_PATH", db_path)
    trigger = {
        "trigger": "per_sub_action_desync_move",
        "tier": 2,
        "severity": "low",
        "details": "legacy shape",
    }
    analysis.append_to_failure_db(
        [trigger], run_id="tr", mission_index=0, turn=1,
        context={"squad": "Rift", "island": "", "model_gap": False,
                 "weight_version": "v?", "solver_version": "v?", "tags": []},
    )
    rec = json.loads(db_path.read_text().strip())
    assert rec.get("fuzzy_signal") is None
