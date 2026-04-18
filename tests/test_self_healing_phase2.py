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


def test_enqueue_research_same_type_different_slot_is_separate():
    """mech_weapon probes for the same mech at different slots coexist."""
    s = RunSession()
    s.enqueue_research("ArtilleryMech", None, current_turn=1,
                       kind="mech_weapon", slot=0)
    s.enqueue_research("ArtilleryMech", None, current_turn=1,
                       kind="mech_weapon", slot=1)
    assert len(s.research_queue) == 2


def test_enqueue_research_same_kind_slot_dedups():
    s = RunSession()
    assert s.enqueue_research("TestMech", None, current_turn=1,
                              kind="mech_weapon", slot=0) is True
    assert s.enqueue_research("TestMech", None, current_turn=2,
                              kind="mech_weapon", slot=0) is False
    assert len(s.research_queue) == 1


def test_enqueue_research_kind_vs_no_kind_are_different_entries():
    """A legacy unit entry and a mech_weapon probe don't alias."""
    s = RunSession()
    s.enqueue_research("TestMech", None, current_turn=1)
    s.enqueue_research("TestMech", None, current_turn=1,
                       kind="mech_weapon", slot=0)
    assert len(s.research_queue) == 2


def test_auto_enqueue_mech_weapons_covers_each_unique_mech_type():
    """One probe per (mech_type, probeable_slot). Duplicate mech types collapse."""
    from types import SimpleNamespace
    from src.loop.commands import _auto_enqueue_mech_weapons
    from src.research.capture import PROBEABLE_WEAPON_SLOTS

    s = RunSession()
    board = SimpleNamespace(units=[
        SimpleNamespace(type="PunchMech", x=0, y=0, hp=3, is_mech=True),
        SimpleNamespace(type="CannonMech", x=1, y=0, hp=3, is_mech=True),
        # Duplicate type — should NOT double-enqueue.
        SimpleNamespace(type="PunchMech", x=2, y=0, hp=3, is_mech=True),
    ])
    enqueued = _auto_enqueue_mech_weapons(s, board, turn_for_queue=1)
    # 2 unique mech types × len(PROBEABLE_WEAPON_SLOTS) slots each.
    assert len(enqueued) == 2 * len(PROBEABLE_WEAPON_SLOTS)
    types_enqueued = {e["type"] for e in enqueued}
    assert types_enqueued == {"PunchMech", "CannonMech"}
    # Every queue entry is kind=mech_weapon with slot in the probeable set.
    for e in s.research_queue:
        assert e["kind"] == "mech_weapon"
        assert e["slot"] in PROBEABLE_WEAPON_SLOTS


def test_auto_enqueue_mech_weapons_skips_nonprobeable_slots():
    """Slot 0 (Repair on the current calibration) is NOT auto-enqueued."""
    from types import SimpleNamespace
    from src.loop.commands import _auto_enqueue_mech_weapons

    s = RunSession()
    board = SimpleNamespace(units=[
        SimpleNamespace(type="M", x=0, y=0, hp=3, is_mech=True),
    ])
    _auto_enqueue_mech_weapons(s, board, turn_for_queue=1)
    slots_in_queue = {e["slot"] for e in s.research_queue}
    assert 0 not in slots_in_queue, \
        "Repair slot should not be auto-enqueued with current calibration"


def test_auto_enqueue_mech_weapons_skips_dead_mechs():
    from types import SimpleNamespace
    from src.loop.commands import _auto_enqueue_mech_weapons

    s = RunSession()
    board = SimpleNamespace(units=[
        SimpleNamespace(type="DeadMech", x=0, y=0, hp=0, is_mech=True),
    ])
    enqueued = _auto_enqueue_mech_weapons(s, board, turn_for_queue=1)
    assert enqueued == []
    assert s.research_queue == []


def test_auto_enqueue_mech_weapons_skips_enemies():
    from types import SimpleNamespace
    from src.loop.commands import _auto_enqueue_mech_weapons

    s = RunSession()
    board = SimpleNamespace(units=[
        SimpleNamespace(type="Hornet1", x=0, y=0, hp=3, is_mech=False),
    ])
    enqueued = _auto_enqueue_mech_weapons(s, board, turn_for_queue=1)
    assert enqueued == []


def test_auto_enqueue_mech_weapons_idempotent_across_calls():
    """Re-reading the same board doesn't re-enqueue existing probes."""
    from types import SimpleNamespace
    from src.loop.commands import _auto_enqueue_mech_weapons
    from src.research.capture import PROBEABLE_WEAPON_SLOTS

    s = RunSession()
    board = SimpleNamespace(units=[
        SimpleNamespace(type="M", x=0, y=0, hp=3, is_mech=True),
    ])
    first = _auto_enqueue_mech_weapons(s, board, turn_for_queue=1)
    second = _auto_enqueue_mech_weapons(s, board, turn_for_queue=2)
    assert len(first) == len(PROBEABLE_WEAPON_SLOTS)
    assert second == []
    assert len(s.research_queue) == len(PROBEABLE_WEAPON_SLOTS)


def test_mark_research_matches_kind_slot():
    s = RunSession()
    s.enqueue_research("Mech", None, current_turn=1,
                       kind="mech_weapon", slot=0)
    s.enqueue_research("Mech", None, current_turn=1,
                       kind="mech_weapon", slot=1)
    assert s.mark_research("Mech", None, "done",
                           kind="mech_weapon", slot=1) is True
    entries = {e["slot"]: e["status"] for e in s.research_queue}
    assert entries[0] == "pending"
    assert entries[1] == "done"


def test_research_queue_persists_across_mission_boundary():
    # Unlike disabled_actions (which reset), the queue is a run-level
    # TODO list — a novel unit seen in mission A is still worth
    # researching in mission B.
    s = RunSession(current_mission="Archive 1")
    s.enqueue_research("FireflyBoss", None, current_turn=2)
    s.advance_mission("Archive 2")
    assert len(s.research_queue) == 1
    assert s.research_queue[0]["type"] == "FireflyBoss"


# ── #P2-7 auto_turn investigating status line ────────────────────────────────


def test_research_peek_returns_first_pending_entries():
    from src.loop.commands import _research_peek
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.enqueue_research("B", None, current_turn=1)
    s.enqueue_research("C", None, current_turn=1)
    peek = _research_peek(s, limit=2)
    assert [p["type"] for p in peek] == ["A", "B"]


def test_research_peek_includes_in_progress_entries():
    # The status line should show "in_progress" entries so the user
    # knows research is active, not just queued.
    from src.loop.commands import _research_peek
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.mark_research("A", None, "in_progress")
    peek = _research_peek(s)
    assert len(peek) == 1
    assert peek[0]["status"] == "in_progress"


def test_research_peek_excludes_done_entries():
    from src.loop.commands import _research_peek
    s = RunSession()
    s.enqueue_research("A", None, current_turn=1)
    s.enqueue_research("B", None, current_turn=1)
    s.mark_research("A", None, "done")
    peek = _research_peek(s)
    assert [p["type"] for p in peek] == ["B"]


def test_narrator_investigating_line_on_pending_entry(capsys):
    from src.loop.commands import _narrate_fuzzy
    peek = [{
        "type": "FireflyBoss",
        "terrain_id": None,
        "status": "pending",
        "attempts": 0,
        "first_seen_turn": 1,
    }]
    _narrate_fuzzy([], [], {}, research_peek=peek)
    out = capsys.readouterr().out
    assert "INVESTIGATING" in out
    assert "FireflyBoss" in out
    assert "not yet researched" in out


def test_narrator_investigating_line_shows_attempt_count(capsys):
    from src.loop.commands import _narrate_fuzzy
    peek = [{
        "type": "FireflyBoss",
        "terrain_id": None,
        "status": "in_progress",
        "attempts": 2,
        "first_seen_turn": 1,
    }]
    _narrate_fuzzy([], [], {}, research_peek=peek)
    out = capsys.readouterr().out
    assert "INVESTIGATING [in_progress]" in out
    assert "attempt 2" in out


def test_narrator_research_peek_alone_still_prints(capsys):
    # Previously the narrator was silent when nothing else fired.
    # With research entries, we should still surface them.
    from src.loop.commands import _narrate_fuzzy
    peek = [{"type": "X", "terrain_id": None, "status": "pending",
             "attempts": 0, "first_seen_turn": 1}]
    _narrate_fuzzy([], [], {}, research_peek=peek)
    assert capsys.readouterr().out != ""
