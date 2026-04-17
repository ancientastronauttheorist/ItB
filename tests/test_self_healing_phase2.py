"""Phase 2 self-healing loop research pipeline tests.

Covers the Phase 2 scaffolding introduced by the ``research_queue``
ticket (#P2-2). Each test exercises Python-only behavior — the
tooltip-capture MCP sequence and Claude Vision extraction land in
#P2-3 and #P2-4 and will get their own fixtures.

Invariants being protected here:

1. Queue round-trips through the session serializer (old sessions
   without the field still load).
2. Dedup key is ``(type, terrain_id)`` — no duplicate research for
   the same pair even if it's re-seen every turn.
3. The ``next_research_entry`` picker returns pending entries in FIFO
   order and skips ``in_progress`` / ``done`` / ``failed`` entries so
   recursive discovery can't fan out.
4. ``mark_research`` transitions bump ``attempts`` only on the
   ``pending → in_progress`` edge, so retrying a deferred entry still
   counts against the retry budget.
5. Mission boundaries DO NOT clear the queue (unlike
   ``disabled_actions``). The queue is a run-level TODO list.
"""

from __future__ import annotations

from src.loop.session import RunSession


def test_research_queue_round_trips():
    s = RunSession(run_id="t", current_mission="M1", current_turn=3)
    s.enqueue_research("FireflyBoss", None, current_turn=3)
    s.enqueue_research("", "quicksand", current_turn=3)
    d = s.to_dict()
    assert len(d["research_queue"]) == 2
    s2 = RunSession.from_dict(d)
    assert len(s2.research_queue) == 2
    assert s2.research_queue[0]["type"] == "FireflyBoss"
    assert s2.research_queue[0]["terrain_id"] is None
    assert s2.research_queue[1]["type"] == ""
    assert s2.research_queue[1]["terrain_id"] == "quicksand"


def test_research_queue_default_empty_on_legacy_session_dict():
    # A dict written before Phase 2 existed (no key) must still load.
    legacy = {"run_id": "old", "squad": "Rift"}
    s = RunSession.from_dict(legacy)
    assert s.research_queue == []


def test_enqueue_research_new_entry_populates_metadata():
    s = RunSession(current_mission="Archive")
    added = s.enqueue_research("Scarab2", None, current_turn=4)
    assert added is True
    e = s.research_queue[0]
    assert e["type"] == "Scarab2"
    assert e["terrain_id"] is None
    assert e["mission_id"] == "Archive"
    assert e["first_seen_turn"] == 4
    assert e["attempts"] == 0
    assert e["status"] == "pending"
    assert e["result"] is None


def test_enqueue_research_dedups_by_type_and_terrain():
    s = RunSession()
    # Same type, same terrain → dupe
    assert s.enqueue_research("FireflyBoss", None, current_turn=1) is True
    assert s.enqueue_research("FireflyBoss", None, current_turn=2) is False
    assert len(s.research_queue) == 1
    # first_seen_turn is NOT overwritten on a re-seen dupe — the first
    # sighting is the interesting data point.
    assert s.research_queue[0]["first_seen_turn"] == 1


def test_enqueue_research_distinguishes_unit_and_terrain_entries():
    s = RunSession()
    # Terrain-only entry shares no key with unit-only entry.
    s.enqueue_research("Scarab2", None, current_turn=1)
    s.enqueue_research("", "quicksand", current_turn=1)
    assert len(s.research_queue) == 2


def test_enqueue_research_same_type_different_terrain_is_separate():
    # Hypothetical: "Volatile Vek" on lava is a different research
    # target than the same unit on ground. Dedup key is the pair.
    s = RunSession()
    s.enqueue_research("VolatileVek", "lava", current_turn=1)
    s.enqueue_research("VolatileVek", "ground", current_turn=1)
    assert len(s.research_queue) == 2


def test_next_research_entry_returns_first_pending():
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.enqueue_research("B", None, current_turn=2)
    first = s.next_research_entry()
    assert first is not None
    assert first["type"] == "A"


def test_next_research_entry_skips_in_progress_and_done():
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.enqueue_research("B", None, current_turn=2)
    s.enqueue_research("C", None, current_turn=3)
    s.mark_research("A", None, "done", result={"ok": True})
    s.mark_research("B", None, "in_progress")
    # A and B are not pickable; C is next.
    nxt = s.next_research_entry()
    assert nxt is not None
    assert nxt["type"] == "C"


def test_next_research_entry_none_when_queue_drained():
    s = RunSession()
    assert s.next_research_entry() is None
    s.enqueue_research("A", None, current_turn=1)
    s.mark_research("A", None, "done")
    assert s.next_research_entry() is None


def test_mark_research_bumps_attempts_on_in_progress_transition():
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.mark_research("A", None, "in_progress")
    assert s.research_queue[0]["attempts"] == 1
    # pending again (deferred) then back to in_progress → attempts=2
    s.mark_research("A", None, "pending")
    assert s.research_queue[0]["attempts"] == 1  # pending transition doesn't bump
    s.mark_research("A", None, "in_progress")
    assert s.research_queue[0]["attempts"] == 2


def test_mark_research_captures_result_payload():
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.mark_research("A", None, "done", result={"name": "Alpha", "hp": 3})
    entry = s.research_queue[0]
    assert entry["status"] == "done"
    assert entry["result"] == {"name": "Alpha", "hp": 3}


def test_mark_research_nonexistent_entry_returns_false():
    s = RunSession()
    assert s.mark_research("Ghost", None, "done") is False


def test_research_queue_persists_across_mission_boundary():
    # Unlike disabled_actions (which reset), the queue is a run-level
    # TODO list — a novel unit seen in mission A is still worth
    # researching in mission B.
    s = RunSession(current_mission="Archive 1")
    s.enqueue_research("FireflyBoss", None, current_turn=2)
    s.advance_mission("Archive 2")
    assert len(s.research_queue) == 1
    assert s.research_queue[0]["type"] == "FireflyBoss"
