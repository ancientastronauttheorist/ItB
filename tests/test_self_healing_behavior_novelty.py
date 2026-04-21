"""Behavior-novelty route tests — Missing wire #5.

Covers the two helpers that close this wire:

1. ``fuzzy_detector.extract_behavior_novelty(diff)`` — returns unit
   types with alive-field flips. Smoking-gun desyncs (predicted kill
   didn't happen, or a unit died we didn't expect) get enqueued for
   research.

2. ``research.orchestrator.has_actionable_research(session, board)``
   — the gate predicate used by ``cmd_read`` to fire the research
   gate when the queue carries entries that the name-novelty detector
   didn't flag this turn (most notably ``behavior_novelty`` entries
   from prior turns' desyncs).

See ``docs/self_healing_loop_design.md`` §Missing wire and CLAUDE.md
rule 20.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.loop.session import RunSession
from src.research import orchestrator
from src.solver import fuzzy_detector
from src.solver.verify import DiffResult


# ── extract_behavior_novelty ─────────────────────────────────────────────────


def test_extract_behavior_novelty_empty_diff():
    diff = DiffResult()
    assert fuzzy_detector.extract_behavior_novelty(diff) == []


def test_extract_behavior_novelty_flags_enemy_survived():
    diff = DiffResult()
    diff.unit_diffs = [{
        "uid": 4, "type": "Scorpion1", "field": "alive",
        "predicted": False, "actual": True,
    }]
    assert fuzzy_detector.extract_behavior_novelty(diff) == ["Scorpion1"]


def test_extract_behavior_novelty_flags_mech_died():
    diff = DiffResult()
    diff.unit_diffs = [{
        "uid": 0, "type": "PunchMech", "field": "alive",
        "predicted": True, "actual": False,
    }]
    assert fuzzy_detector.extract_behavior_novelty(diff) == ["PunchMech"]


def test_extract_behavior_novelty_ignores_non_alive_flips():
    # HP mismatch is a magnitude bug — tier-2 soft-disable handles it,
    # not the research pipeline. Only alive flips count.
    diff = DiffResult()
    diff.unit_diffs = [{
        "uid": 4, "type": "Scorpion1", "field": "hp",
        "predicted": 1, "actual": 2,
    }]
    assert fuzzy_detector.extract_behavior_novelty(diff) == []


def test_extract_behavior_novelty_dedupes_and_sorts():
    diff = DiffResult()
    diff.unit_diffs = [
        {"uid": 4, "type": "Scorpion1", "field": "alive",
         "predicted": False, "actual": True},
        {"uid": 5, "type": "Firefly1", "field": "alive",
         "predicted": False, "actual": True},
        {"uid": 6, "type": "Scorpion1", "field": "alive",  # dupe type
         "predicted": True, "actual": False},
    ]
    assert fuzzy_detector.extract_behavior_novelty(diff) == ["Firefly1", "Scorpion1"]


# ── has_actionable_research ──────────────────────────────────────────────────


def _fake_board(unit_types: list[str] | None = None):
    """Minimal board duck-type for orchestrator helpers."""
    unit_types = unit_types or []
    units = [
        SimpleNamespace(type=t, hp=1, x=0, y=0, is_mech=False)
        for t in unit_types
    ]
    tiles = [[SimpleNamespace(terrain="ground") for _ in range(8)] for _ in range(8)]
    return SimpleNamespace(units=units, tiles=tiles)


def test_actionable_false_on_empty_queue():
    s = RunSession()
    assert orchestrator.has_actionable_research(s, _fake_board()) is False


def test_actionable_true_when_behavior_target_on_board():
    s = RunSession()
    s.enqueue_research("Scorpion1", None, 1, kind="behavior_novelty")
    board = _fake_board(["Scorpion1"])
    assert orchestrator.has_actionable_research(s, board) is True


def test_actionable_false_when_behavior_target_absent():
    s = RunSession()
    s.enqueue_research("Scorpion1", None, 1, kind="behavior_novelty")
    board = _fake_board(["Firefly1"])  # different unit on board
    assert orchestrator.has_actionable_research(s, board) is False


def test_actionable_false_for_background_mech_weapon_probe():
    # mech_weapon probes are background; they should NOT trip the gate
    # even with a matching unit on the board. Otherwise every run would
    # gate turn 1 on its own mechs.
    s = RunSession()
    s.enqueue_research("PunchMech", None, 1, kind="mech_weapon", slot=1)
    board = _fake_board(["PunchMech"])
    assert orchestrator.has_actionable_research(s, board) is False


def test_actionable_false_for_done_entries():
    # A resolved entry stays on the queue; it must not keep firing the gate.
    s = RunSession()
    s.enqueue_research("Scorpion1", None, 1, kind="behavior_novelty")
    s.mark_research(
        "Scorpion1", None, "done", result={},
        kind="behavior_novelty",
    )
    board = _fake_board(["Scorpion1"])
    assert orchestrator.has_actionable_research(s, board) is False


def test_actionable_true_for_terrain_entry_on_board():
    # Legacy terrain-only entry (type="", kind=None) should still fire
    # the gate as long as the terrain is present on the board.
    s = RunSession()
    s.enqueue_research("", "quicksand", 1)
    board = _fake_board()
    board.tiles[3][3].terrain = "quicksand"
    assert orchestrator.has_actionable_research(s, board) is True
