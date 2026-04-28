"""Fix B (2026-04-28): load-time backfill of the soft-disable per-run cap.

Background: ``_SOFT_DISABLE_PER_RUN_CAP`` was prospective only —
pre-existing entries in ``disabled_actions`` were left in place when the
session loaded. Run 2's session inherited 4 active entries from Run 1
(different squad), each shaving ~10000 from any plan that touched the
weapon. Per the Run-2 forensics, every solve started at a -40k score
floor, distorting search.

This file regression-tests the fix:

  * ``RunSession.from_dict`` prunes ``disabled_actions`` down to
    ``DISABLED_ACTIONS_CAP`` if the file is over-cap. Pruning preserves
    the highest-confidence entries (lowest dropped).
  * Loading a session at-or-under the cap is a no-op.
  * ``cmd_new_run`` produces a session with ``disabled_actions == []``
    regardless of any persistent state on disk.
  * The prune helper is monotonic (sorted by confidence asc, stable on
    ties) and idempotent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop import commands
from src.loop.session import (
    DISABLED_ACTIONS_CAP,
    RunSession,
    _prune_disabled_actions_to_cap,
)


# ── Load-time prune ──────────────────────────────────────────────────────────


def _entry(weapon: str, *, confidence: float | None = None,
           expires_turn: int = 5,
           cause: str = "stale|cause") -> dict:
    """Build a disabled_actions entry; optional confidence field."""
    e: dict = {
        "weapon_id": weapon,
        "cause_pattern": cause,
        "expires_turn": expires_turn,
        "strategic_override": False,
    }
    if confidence is not None:
        e["confidence"] = confidence
    return e


def test_load_session_with_four_entries_prunes_to_cap():
    """The Run-2-on-disk shape: 4 disabled_actions, no per-entry confidence.
    All entries tie on confidence (=0.0 default), so we fall back to
    expires_turn (earliest expires drops first) then insertion order.

    Drop pile (first ``len-cap == 2`` after ascending sort by
    ``(confidence, expires_turn, insertion_idx)``):
      1. ``(0.0, 6, 2)`` Brute_Grapple   — earliest expiry
      2. ``(0.0, 7, 0)`` Science_Gravwell — first inserted among the rest

    Kept (preserving original insertion order via the stability re-sort):
      Ranged_Artillerymech, Prime_Shift.
    """
    payload = {
        "disabled_actions": [
            _entry("Science_Gravwell", expires_turn=7),
            _entry("Ranged_Artillerymech", expires_turn=7),
            _entry("Brute_Grapple", expires_turn=6),
            _entry("Prime_Shift", expires_turn=7),
        ],
    }
    s = RunSession.from_dict(payload)
    assert len(s.disabled_actions) == DISABLED_ACTIONS_CAP == 2
    weapons = [e["weapon_id"] for e in s.disabled_actions]
    assert "Brute_Grapple" not in weapons
    assert "Science_Gravwell" not in weapons
    assert weapons == ["Ranged_Artillerymech", "Prime_Shift"]


def test_load_session_at_cap_is_noop():
    """Two entries → no prune."""
    payload = {
        "disabled_actions": [
            _entry("W1", confidence=0.9),
            _entry("W2", confidence=0.9),
        ],
    }
    s = RunSession.from_dict(payload)
    assert len(s.disabled_actions) == 2
    assert {e["weapon_id"] for e in s.disabled_actions} == {"W1", "W2"}


def test_load_session_under_cap_is_noop():
    """One entry → no prune."""
    payload = {"disabled_actions": [_entry("W1", confidence=0.9)]}
    s = RunSession.from_dict(payload)
    assert len(s.disabled_actions) == 1


def test_load_session_empty_is_noop():
    """No entries → no crash, empty list."""
    s = RunSession.from_dict({})
    assert s.disabled_actions == []
    s = RunSession.from_dict({"disabled_actions": []})
    assert s.disabled_actions == []


def test_load_drops_lowest_confidence_first():
    """When confidence is stored, lowest-confidence entries drop first."""
    payload = {
        "disabled_actions": [
            _entry("Keep1", confidence=0.95),
            _entry("Drop1", confidence=0.55),
            _entry("Drop2", confidence=0.50),
            _entry("Keep2", confidence=0.90),
        ],
    }
    s = RunSession.from_dict(payload)
    weapons = {e["weapon_id"] for e in s.disabled_actions}
    assert weapons == {"Keep1", "Keep2"}


# ── new_run wipes the list ───────────────────────────────────────────────────


def test_cmd_new_run_clears_disabled_actions(tmp_path, monkeypatch):
    """Calling cmd_new_run produces a session with disabled_actions=[].

    Even if a stale on-disk session has 4 entries (Run-2 shape), the new
    run starts clean — squad has changed, prior soft-disables are
    irrelevant.

    We capture the session that ``cmd_new_run`` saves by intercepting
    ``RunSession.save`` rather than redirecting the on-disk path: the
    ``save()`` default-arg binds to the module-level
    ``DEFAULT_SESSION_FILE`` at definition time and would otherwise
    clobber the real sessions/active_session.json.
    """
    captured: list = []

    def fake_save(self, path=None):
        # Capture a snapshot of the in-memory session being saved.
        captured.append({
            "disabled_actions": list(self.disabled_actions),
            "squad": self.squad,
            "run_id": self.run_id,
        })

    monkeypatch.setattr(RunSession, "save", fake_save)
    # Stub the decision logger so we don't write to logs/.
    monkeypatch.setattr(commands, "DecisionLog",
                        lambda run_id: type("Stub", (), {
                            "log_custom": lambda self, *a, **k: None,
                        })())
    # Stub _write_manifest to no-op.
    monkeypatch.setattr(commands, "_write_manifest", lambda s, **k: None)

    # NOTE: cmd_new_run constructs a fresh RunSession via
    # ``RunSession.new_run`` (NOT via load), so any pre-existing
    # disabled_actions on disk are irrelevant — the new session starts
    # with the dataclass default ``[]``. We verify that contract here:
    # even after we explicitly seed disables (simulating a pathological
    # future refactor that inherits prior session fields) the explicit
    # wipe in cmd_new_run still produces an empty list.

    # Seed the in-memory pre-save state by monkey-patching new_run to
    # return a session pre-loaded with stale entries. This mimics a
    # hypothetical future regression.
    real_new_run = RunSession.new_run

    def seeded_new_run(squad, achievements=None, difficulty=0, tags=None):
        s = real_new_run(squad, achievements, difficulty, tags=tags)
        s.disabled_actions = [
            _entry("Stale1", confidence=0.9, expires_turn=10),
            _entry("Stale2", confidence=0.9, expires_turn=10),
            _entry("Stale3", confidence=0.9, expires_turn=10),
            _entry("Stale4", confidence=0.9, expires_turn=10),
        ]
        return s

    monkeypatch.setattr(RunSession, "new_run", classmethod(
        lambda cls, *a, **kw: seeded_new_run(*a, **kw)
    ))

    commands.cmd_new_run("Rift Walkers", achievements=[], difficulty=0)

    assert captured, "cmd_new_run did not call save"
    saved = captured[-1]
    assert saved["disabled_actions"] == []
    assert saved["squad"] == "Rift Walkers"


# ── Helper invariants ────────────────────────────────────────────────────────


def test_prune_helper_sorts_by_confidence_ascending():
    """_prune_disabled_actions_to_cap drops lowest-confidence first."""
    entries = [
        _entry("Drop_low", confidence=0.1),
        _entry("Keep_high", confidence=0.95),
        _entry("Drop_mid", confidence=0.5),
        _entry("Keep_higher", confidence=0.99),
    ]
    out = _prune_disabled_actions_to_cap(entries, cap=2, reason="test",
                                         log=False)
    weapons = [e["weapon_id"] for e in out]
    assert "Drop_low" not in weapons
    assert "Drop_mid" not in weapons
    assert set(weapons) == {"Keep_high", "Keep_higher"}


def test_prune_helper_stable_on_ties():
    """Equal confidence + equal expiry → kept entries preserve insertion
    order (stability)."""
    entries = [
        _entry("First", confidence=0.5, expires_turn=5),
        _entry("Second", confidence=0.5, expires_turn=5),
        _entry("Third", confidence=0.5, expires_turn=5),
    ]
    out = _prune_disabled_actions_to_cap(entries, cap=2, reason="test",
                                         log=False)
    # The drop pile takes the FIRST entry (it sorts to the head — same
    # priority but earlier insertion = drop). The KEPT entries — Second,
    # Third — preserve their insertion order.
    assert [e["weapon_id"] for e in out] == ["Second", "Third"]


def test_prune_helper_idempotent():
    """Pruning to cap and pruning again yields the same list (idempotent)."""
    entries = [
        _entry("W1", confidence=0.1),
        _entry("W2", confidence=0.5),
        _entry("W3", confidence=0.9),
    ]
    once = _prune_disabled_actions_to_cap(list(entries), cap=2,
                                          reason="test", log=False)
    twice = _prune_disabled_actions_to_cap(list(once), cap=2,
                                           reason="test", log=False)
    assert [e["weapon_id"] for e in once] == [e["weapon_id"] for e in twice]


def test_prune_helper_under_cap_is_noop():
    """Cap >= len → no entries dropped, list unchanged."""
    entries = [_entry("W1", confidence=0.5)]
    before = list(entries)
    out = _prune_disabled_actions_to_cap(entries, cap=2, reason="test",
                                         log=False)
    assert out == before
    assert [e["weapon_id"] for e in out] == ["W1"]


def test_prune_helper_handles_missing_confidence():
    """Entries without a stored confidence default to 0.0 (lowest);
    expiry then breaks ties so the earliest-expiring drops first."""
    entries = [
        _entry("Late", expires_turn=10),
        _entry("Early", expires_turn=2),
        _entry("Middle", expires_turn=6),
    ]
    out = _prune_disabled_actions_to_cap(entries, cap=2, reason="test",
                                         log=False)
    # All tie on confidence (=0). Drop pile picks the smallest expires
    # (Early). Kept = Late + Middle.
    weapons = [e["weapon_id"] for e in out]
    assert "Early" not in weapons
    assert set(weapons) == {"Late", "Middle"}
