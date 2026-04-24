"""PR4 — Layer 3 auto-trigger queue.

Covers the contract between cmd_verify_action's enqueue and the
harness-driven cmd_diagnose_next drain loop:

  - _enqueue_diagnosis appends to session.diagnosis_queue with a stable
    diff_signature key.
  - Dedup on (diff_signature, sim_version) — same diff in same sim
    version doesn't double-enqueue.
  - model_gap=true desyncs are skipped (Layer 2 would short-circuit
    them to insufficient_data — no point burning a queue slot).
  - Round-trip through to_dict / from_dict so the queue survives
    session save/load.

Marked @pytest.mark.regression so they run with the rest of the corpus
suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop.commands import _enqueue_diagnosis
from src.loop.session import RunSession
from src.solver.diagnosis import combined_diff_signature


def _make_session(tmp_path: Path) -> RunSession:
    s = RunSession(run_id="pr4_test", squad="test_squad", mission_index=0)
    s.diagnosis_queue = []
    return s


def _frozen_diff() -> dict:
    return {
        "unit_diffs": [
            {"uid": 5, "type": "Hornet1", "field": "status.frozen",
             "predicted": True, "actual": False},
        ],
        "tile_diffs": [],
        "scalar_diffs": [],
        "total_count": 1,
    }


def _hp_diff() -> dict:
    return {
        "unit_diffs": [
            {"uid": 7, "type": "Scarab1", "field": "hp",
             "predicted": 1, "actual": 2},
        ],
        "tile_diffs": [],
        "scalar_diffs": [],
        "total_count": 1,
    }


# ---------------------------------------------------------------------------
# Enqueue: shape + dedup + model_gap skip.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_enqueue_appends_pending_entry(tmp_path):
    s = _make_session(tmp_path)
    diff = _frozen_diff()
    classification = {"top_category": "status", "model_gap": False}
    added = _enqueue_diagnosis(
        s, failure_id="fid_1", diff_dict=diff,
        sim_version=10, classification=classification,
    )
    assert added is True
    assert len(s.diagnosis_queue) == 1
    entry = s.diagnosis_queue[0]
    assert entry["failure_id"] == "fid_1"
    assert entry["status"] == "pending"
    assert entry["sim_version"] == 10
    assert entry["diff_signature"] == combined_diff_signature(diff)
    assert entry["diagnose_status"] is None
    assert entry["enqueued_at"].endswith("Z")


@pytest.mark.regression
def test_enqueue_dedups_on_same_diff_and_sim_version(tmp_path):
    s = _make_session(tmp_path)
    diff = _frozen_diff()
    cls = {"top_category": "status", "model_gap": False}

    assert _enqueue_diagnosis(s, "fid_1", diff, 10, cls) is True
    # Same diff, same sim_version, different failure_id (e.g. retry on same turn)
    assert _enqueue_diagnosis(s, "fid_1_retry", diff, 10, cls) is False
    assert len(s.diagnosis_queue) == 1


@pytest.mark.regression
def test_enqueue_separates_different_sim_versions(tmp_path):
    s = _make_session(tmp_path)
    diff = _frozen_diff()
    cls = {"top_category": "status", "model_gap": False}

    assert _enqueue_diagnosis(s, "fid_a", diff, sim_version=10, classification=cls) is True
    # Different sim version — same diff might diagnose differently.
    assert _enqueue_diagnosis(s, "fid_b", diff, sim_version=11, classification=cls) is True
    assert len(s.diagnosis_queue) == 2


@pytest.mark.regression
def test_enqueue_separates_different_diffs(tmp_path):
    s = _make_session(tmp_path)
    cls = {"top_category": "status", "model_gap": False}
    assert _enqueue_diagnosis(s, "f_a", _frozen_diff(), 10, cls) is True
    assert _enqueue_diagnosis(s, "f_b", _hp_diff(), 10, cls) is True
    assert len(s.diagnosis_queue) == 2


@pytest.mark.regression
def test_enqueue_skips_model_gap_desyncs(tmp_path):
    """Layer 2 short-circuits model_gap diffs to insufficient_data —
    no point queueing them up."""
    s = _make_session(tmp_path)
    diff = _frozen_diff()
    cls = {"top_category": "tile_status", "model_gap": True}
    added = _enqueue_diagnosis(s, "fid_gap", diff, 10, cls)
    assert added is False
    assert s.diagnosis_queue == []


# ---------------------------------------------------------------------------
# Session round-trip: queue survives save/load.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_diagnosis_queue_round_trips_through_session_dict(tmp_path):
    s = _make_session(tmp_path)
    cls = {"top_category": "status", "model_gap": False}
    _enqueue_diagnosis(s, "fid_persist", _frozen_diff(), 10, cls)

    session_path = tmp_path / "session.json"
    s.save(session_path)
    s2 = RunSession.load(session_path)

    assert len(s2.diagnosis_queue) == 1
    assert s2.diagnosis_queue[0]["failure_id"] == "fid_persist"
    assert s2.diagnosis_queue[0]["sim_version"] == 10


@pytest.mark.regression
def test_diagnosis_queue_default_empty_for_legacy_session_files(tmp_path):
    """Pre-PR4 session.json files have no diagnosis_queue key — load with []."""
    legacy = {
        "run_id": "legacy",
        "squad": "Punch/Jet/Rocket",
        "mission_index": 0,
    }
    session_path = tmp_path / "legacy_session.json"
    session_path.write_text(json.dumps(legacy))
    s = RunSession.load(session_path)
    assert s.diagnosis_queue == []


# ---------------------------------------------------------------------------
# Drain: the harness loop pops one entry at a time.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_drain_marks_entry_done_with_diagnose_status(tmp_path, monkeypatch):
    """cmd_diagnose_next pops the first pending entry, runs diagnose(),
    and writes the result back into the queue entry."""
    # Isolate the rejections store so the diagnose call can't cross-pollute.
    monkeypatch.setattr(
        "src.solver.diagnosis.REJECTIONS_PATH",
        tmp_path / "rejections.jsonl",
    )

    # Hand-roll a minimal failure_db fixture so diagnose() can find it.
    failure = {
        "id": "drain_test_a0",
        "run_id": "drain_test",
        "mission": 0,
        "turn": 1,
        "action_index": 0,
        "simulator_version": 9,
        "category": "click_miss",
        "diff": {
            "unit_diffs": [
                {"uid": 1, "type": "WallMech", "field": "active",
                 "predicted": False, "actual": True},
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    db_path = tmp_path / "failure_db.jsonl"
    db_path.write_text(json.dumps(failure) + "\n")
    monkeypatch.setattr("src.solver.diagnosis.FAILURE_DB_PATH", db_path)

    # The action lookup goes through load_action_for_failure; stub it so
    # the drain doesn't need a real solve recording on disk.
    action = {
        "mech_uid": 1,
        "mech_type": "WallMech",
        "weapon": "Unknown",
        "weapon_id": "Unknown",
        "target": [255, 255],
        "description": "WallMech move-only fixture",
    }
    monkeypatch.setattr(
        "src.solver.diagnosis.load_action_for_failure",
        lambda f: action,
    )

    # Now the actual drain: build a session that already has the entry
    # enqueued, hand it to cmd_diagnose_next via the standard load path.
    s = _make_session(tmp_path)
    cls = {"top_category": "click_miss", "model_gap": False}
    _enqueue_diagnosis(s, failure["id"], failure["diff"],
                       failure["simulator_version"], cls)
    session_path = tmp_path / "active_session.json"
    s.save(session_path)

    # Patch DEFAULT_SESSION_FILE so cmd_diagnose_next loads our test session.
    # Both modules see it: commands.py uses it on load, session.save's default
    # argument resolves through src.loop.session at definition time so we
    # patch both to keep them consistent.
    monkeypatch.setattr(
        "src.loop.commands.DEFAULT_SESSION_FILE",
        session_path,
    )
    monkeypatch.setattr(
        "src.loop.session.DEFAULT_SESSION_FILE",
        session_path,
    )
    # Diagnose writes markdown under recordings/<run_id>/diagnoses/. Send
    # those writes into tmp_path too.
    diag_out = tmp_path / "diag"
    monkeypatch.setattr(
        "src.solver.diagnosis.RECORDINGS_DIR",
        diag_out,
    )

    from src.loop.commands import cmd_diagnose_next
    result = cmd_diagnose_next()
    assert result["status"] == "OK"
    assert result["failure_id"] == failure["id"]
    # The move_only_active_guard rule should fire (sim_v9, weapon_id=Unknown).
    assert result["diagnose_status"] == "rule_match"
    assert result["rule_id"] == "move_only_active_guard"
    assert result["queue_remaining"] == 0

    # And the persisted session reflects the drain.
    s_after = RunSession.load(session_path)
    assert len(s_after.diagnosis_queue) == 1
    entry = s_after.diagnosis_queue[0]
    assert entry["status"] == "done"
    assert entry["diagnose_status"] == "rule_match"
    assert entry["rule_id"] == "move_only_active_guard"
    assert entry["markdown"] is not None


@pytest.mark.regression
def test_drain_returns_empty_when_queue_drained(tmp_path, monkeypatch):
    s = _make_session(tmp_path)
    session_path = tmp_path / "active_session.json"
    s.save(session_path)
    monkeypatch.setattr("src.loop.commands.DEFAULT_SESSION_FILE", session_path)
    monkeypatch.setattr("src.loop.session.DEFAULT_SESSION_FILE", session_path)

    from src.loop.commands import cmd_diagnose_next
    result = cmd_diagnose_next()
    assert result["status"] == "EMPTY"
