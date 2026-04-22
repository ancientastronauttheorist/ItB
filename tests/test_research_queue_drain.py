"""Severity-gated research queue drain — Fix #4.

Covers ``derive_severity``, ``worst_diff_per_type``, and
``drain_stale_behavior_novelty`` in ``src.research.orchestrator``.

The drain's job is to auto-resolve pending ``behavior_novelty`` entries
whose target type is already catalogued in ``data/known_types.json``
AND whose worst diff this turn was low-severity (off-by-one HP,
position-only). Those entries would otherwise refire the research gate
every turn without giving the Vision pipeline anything new to extract —
the failure_db corpus already captures the signal for the tuner.

High-severity entries (alive flips, push_dir, ≥2 damage gap) and
entries on uncatalogued types stay pending for analyst review. The
predicate ``has_actionable_research`` stays read-only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.loop.session import RunSession
from src.research import orchestrator
from src.solver import unknown_detector
from src.solver.verify import DiffResult


@pytest.fixture(autouse=True)
def _reset_known_types_cache():
    """known_types.json is cached module-wide; drain reads it per call.
    Reset around every test so parallel runs see the real file."""
    unknown_detector.reset_cache()
    yield
    unknown_detector.reset_cache()


# ── derive_severity ─────────────────────────────────────────────────────────


def test_severity_alive_flip_is_high():
    assert orchestrator.derive_severity("alive", True, False) == "high"
    assert orchestrator.derive_severity("alive", False, True) == "high"


def test_severity_push_dir_is_high():
    assert orchestrator.derive_severity("push_dir", "up", "down") == "high"


def test_severity_hp_off_by_one_is_low():
    assert orchestrator.derive_severity("hp", 2, 3) == "low"
    assert orchestrator.derive_severity("hp", 3, 2) == "low"


def test_severity_hp_gap_two_plus_is_high():
    assert orchestrator.derive_severity("hp", 1, 3) == "high"
    assert orchestrator.derive_severity("hp", 4, 1) == "high"


def test_severity_damage_amount_matches_hp_schema():
    assert orchestrator.derive_severity("damage_amount", 1, 2) == "low"
    assert orchestrator.derive_severity("damage_amount", 1, 4) == "high"


def test_severity_position_is_low():
    assert orchestrator.derive_severity("position", [3, 2], [3, 3]) == "low"


def test_severity_unparseable_magnitude_is_medium():
    # Non-numeric predicted/actual on a magnitude field defaults to
    # medium — we can't rank the gap, and high would over-gate.
    assert orchestrator.derive_severity("hp", None, 2) == "medium"
    assert orchestrator.derive_severity("hp", "oops", 2) == "medium"


def test_severity_unknown_field_is_medium():
    assert orchestrator.derive_severity("terrain", "ground", "water") == "medium"


# ── worst_diff_per_type ─────────────────────────────────────────────────────


def test_worst_diff_picks_highest_severity_per_type():
    diff = DiffResult()
    diff.unit_diffs = [
        {"uid": 5, "type": "Scorpion1", "field": "hp",
         "predicted": 2, "actual": 3},  # low
        {"uid": 5, "type": "Scorpion1", "field": "alive",
         "predicted": False, "actual": True},  # high
    ]
    best = orchestrator.worst_diff_per_type(diff)
    assert set(best.keys()) == {"Scorpion1"}
    field, predicted, actual, sev = best["Scorpion1"]
    assert field == "alive"
    assert sev == "high"


def test_worst_diff_skips_friendly_mechs():
    diff = DiffResult()
    diff.unit_diffs = [
        {"uid": 0, "type": "PunchMech", "field": "alive",
         "predicted": True, "actual": False},
        {"uid": 5, "type": "Hornet1", "field": "hp",
         "predicted": 1, "actual": 2},
    ]
    best = orchestrator.worst_diff_per_type(diff)
    assert set(best.keys()) == {"Hornet1"}


def test_worst_diff_empty_for_no_unit_diffs():
    diff = DiffResult()
    assert orchestrator.worst_diff_per_type(diff) == {}


# ── drain_stale_behavior_novelty ────────────────────────────────────────────


def test_drain_resolves_low_severity_known_type(monkeypatch):
    # Scorpion1 is in data/known_types.json observed_pawn_types.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )

    resolved = orchestrator.drain_stale_behavior_novelty(s)

    assert resolved == ["Scorpion1"]
    entry = s.research_queue[0]
    assert entry["status"] == "done"
    assert entry["result"]["source"] == "auto_resolved"
    assert entry["result"]["reason"] == "low_severity_known_type"
    # Diff metadata round-trips onto the resolution payload so
    # post-hoc analysis can join to failure_db without re-reading the queue.
    assert entry["result"]["diff_field"] == "hp"
    assert entry["result"]["diff_predicted"] == 2
    assert entry["result"]["diff_actual"] == 3


def test_drain_keeps_high_severity_known_type(monkeypatch):
    # Scorpion1 (known) surviving a predicted kill IS a genuine bug
    # signal — the user spec calls this out explicitly. Stay pending.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="alive", diff_predicted=False, diff_actual=True,
        severity="high",
    )

    resolved = orchestrator.drain_stale_behavior_novelty(s)

    assert resolved == []
    assert s.research_queue[0]["status"] == "pending"


def test_drain_keeps_unknown_type_low_severity(monkeypatch):
    # Unknown type with low-severity diff still stays pending —
    # catalogues come from research, not from the drain.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "TotallyMadeUpEnemy", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )

    resolved = orchestrator.drain_stale_behavior_novelty(s)

    assert resolved == []
    assert s.research_queue[0]["status"] == "pending"


def test_drain_ignores_medium_severity(monkeypatch):
    # Only "low" drains. Medium is the default for unclassified diffs
    # and must stay pending so the analyst can triage.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="terrain", diff_predicted="ground", diff_actual="water",
        severity="medium",
    )

    assert orchestrator.drain_stale_behavior_novelty(s) == []
    assert s.research_queue[0]["status"] == "pending"


def test_drain_ignores_non_behavior_novelty_kinds(monkeypatch):
    # mech_weapon probes are background — they shouldn't ever flow
    # through the drain even if someone accidentally stamps severity.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "ChargeMech", None, 1, kind="mech_weapon", slot=1,
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )

    assert orchestrator.drain_stale_behavior_novelty(s) == []
    assert s.research_queue[0]["status"] == "pending"


def test_drain_ignores_already_resolved_entries(monkeypatch):
    # A previously-resolved entry must not count as drained again on
    # re-scan — the return value feeds the "research_auto_resolved"
    # field on cmd_read output and would double-report.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )
    s.research_queue[0]["status"] = "done"

    assert orchestrator.drain_stale_behavior_novelty(s) == []


def test_drain_saves_session_once_when_anything_resolved(monkeypatch):
    save_calls: list = []
    monkeypatch.setattr(
        RunSession, "save",
        lambda self, *a, **kw: save_calls.append(True),
    )
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )
    s.enqueue_research(
        "Hornet1", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=1, diff_actual=2,
        severity="low",
    )

    resolved = orchestrator.drain_stale_behavior_novelty(s)

    # Two entries drained → save() called exactly once, not per entry.
    assert sorted(resolved) == ["Hornet1", "Scorpion1"]
    assert len(save_calls) == 1


def test_drain_no_save_when_nothing_resolved(monkeypatch):
    # Idempotent no-op: never touches disk when the queue is clean.
    save_calls: list = []
    monkeypatch.setattr(
        RunSession, "save",
        lambda self, *a, **kw: save_calls.append(True),
    )
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="alive", diff_predicted=False, diff_actual=True,
        severity="high",
    )

    assert orchestrator.drain_stale_behavior_novelty(s) == []
    assert save_calls == []


def test_drain_legacy_entries_without_severity_stay_pending(monkeypatch):
    # Old session files may have behavior_novelty entries predating
    # the severity stamp. Those can't be safely auto-resolved — missing
    # severity means we don't know what kind of mispredict it was, so
    # the safe default is to leave them for the analyst.
    monkeypatch.setattr(RunSession, "save", lambda self, *a, **kw: None)
    s = RunSession()
    s.enqueue_research("Scorpion1", None, 1, kind="behavior_novelty")

    assert orchestrator.drain_stale_behavior_novelty(s) == []
    assert s.research_queue[0]["status"] == "pending"
    assert "severity" not in s.research_queue[0]


# ── predicate stays read-only ───────────────────────────────────────────────


def _fake_board(unit_types: list[str] | None = None):
    unit_types = unit_types or []
    units = [
        SimpleNamespace(type=t, hp=1, x=0, y=0, is_mech=False)
        for t in unit_types
    ]
    tiles = [
        [SimpleNamespace(terrain="ground") for _ in range(8)] for _ in range(8)
    ]
    return SimpleNamespace(units=units, tiles=tiles)


def test_has_actionable_research_does_not_mutate_queue():
    # Regression guard for Fix #4: the drain is the sole mutator of the
    # queue during a cmd_read cycle. Any mutation side effect smuggled
    # into the predicate (e.g. attempts++ or status flip) would break
    # existing orchestrator tests and violate the read-only contract.
    s = RunSession()
    s.enqueue_research(
        "Scorpion1", None, 1, kind="behavior_novelty",
        diff_field="hp", diff_predicted=2, diff_actual=3,
        severity="low",
    )
    board = _fake_board(["Scorpion1"])
    snapshot = [dict(e) for e in s.research_queue]

    _ = orchestrator.has_actionable_research(s, board)

    assert [dict(e) for e in s.research_queue] == snapshot
