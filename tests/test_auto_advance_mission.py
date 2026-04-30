"""Unit tests for ``_auto_advance_mission``.

The helper is the safety net that keeps multi-mission runs from clobbering
their own recordings. Without it, every mission in a run shares
``mission_index=0`` and ``m00_turn_*`` files get overwritten — see run
20260428_165811_685 where Mission_FreezeBots overwrote Mission_BotDefense.

Test the four behavior cases:

1. Empty bridge ``mission_id`` → no-op (between-missions / loading state).
2. First mission this run (``current_mission`` empty) → adopt name, do
   NOT bump ``mission_index`` (it already points at slot 0).
3. Same mission_id observed again → no-op (every-turn read path).
4. Different mission_id while ``current_mission`` is set → mission
   boundary the harness missed; bump index, adopt name, clear
   ``disabled_actions``.
"""

from src.loop.commands import _auto_advance_mission
from src.loop.session import RunSession


def _fresh_session(**overrides) -> RunSession:
    s = RunSession(run_id="test_run", squad="rift_walkers")
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_empty_mission_id_is_noop():
    s = _fresh_session(current_mission="Mission_Survive", mission_index=2)
    changed = _auto_advance_mission(s, {"mission_id": ""})
    assert changed is False
    assert s.current_mission == "Mission_Survive"
    assert s.mission_index == 2


def test_missing_mission_id_key_is_noop():
    s = _fresh_session(current_mission="Mission_Survive", mission_index=2)
    changed = _auto_advance_mission(s, {})
    assert changed is False
    assert s.current_mission == "Mission_Survive"
    assert s.mission_index == 2


def test_first_mission_adopts_name_without_bumping():
    """Fresh run, mission_index=0, current_mission empty.

    First bridge read with mission_id should set the name but leave
    mission_index at 0 so the first mission's recordings land under m00_*.
    """
    s = _fresh_session(current_mission="", mission_index=0)
    changed = _auto_advance_mission(s, {"mission_id": "Mission_FreezeBots"})
    assert changed is True
    assert s.current_mission == "Mission_FreezeBots"
    assert s.mission_index == 0


def test_post_mission_end_re_entry_adopts_name_at_pre_bumped_index():
    """``cmd_mission_end`` clears current_mission and bumps mission_index.

    When the next mission starts, _auto_advance_mission should adopt the
    new name without re-bumping (the index is already correct).
    """
    s = _fresh_session(current_mission="", mission_index=3)
    changed = _auto_advance_mission(s, {"mission_id": "Mission_FreezeBots"})
    assert changed is True
    assert s.current_mission == "Mission_FreezeBots"
    assert s.mission_index == 3


def test_same_mission_id_is_noop():
    s = _fresh_session(current_mission="Mission_Survive", mission_index=2)
    changed = _auto_advance_mission(s, {"mission_id": "Mission_Survive"})
    assert changed is False
    assert s.current_mission == "Mission_Survive"
    assert s.mission_index == 2


def test_mission_boundary_bumps_and_clears_blocklist():
    """The bug case: harness skipped cmd_mission_end.

    Bridge reports a different mission_id while current_mission is set —
    we missed the Region Secured screen. Bump and reset.
    """
    s = _fresh_session(
        current_mission="Mission_BotDefense",
        mission_index=0,
        disabled_actions=[
            {"weapon_id": "Brute_Sniper", "expires_turn": 999,
             "cause": "test"},
        ],
    )
    changed = _auto_advance_mission(s, {"mission_id": "Mission_FreezeBots"})
    assert changed is True
    assert s.current_mission == "Mission_FreezeBots"
    assert s.mission_index == 1
    assert s.disabled_actions == []


def test_repeated_boundary_each_bumps_once():
    """Three missions in a row → indices 0, 1, 2."""
    s = _fresh_session(current_mission="", mission_index=0)
    _auto_advance_mission(s, {"mission_id": "Mission_BotDefense"})
    assert s.mission_index == 0
    assert s.current_mission == "Mission_BotDefense"
    _auto_advance_mission(s, {"mission_id": "Mission_FreezeBots"})
    assert s.mission_index == 1
    _auto_advance_mission(s, {"mission_id": "Mission_Volatile"})
    assert s.mission_index == 2
    assert s.current_mission == "Mission_Volatile"


def test_whitespace_mission_id_treated_as_empty():
    s = _fresh_session(current_mission="Mission_Survive", mission_index=2)
    changed = _auto_advance_mission(s, {"mission_id": "   "})
    assert changed is False
    assert s.current_mission == "Mission_Survive"
    assert s.mission_index == 2


# --- Same-template, new-instance detection (turn-regression) ---


def test_same_template_turn_regression_bumps_index():
    """Bridge mission_id matches current_mission but bridge.turn drops below
    the highest turn we observed. This is the volcano-final / recurring-
    template collision: harness skipped cmd_mission_end AND the next mission
    happens to share the template id (e.g., Mission_Acid on island 1 then
    again on island 2). Without the regression check, mission_index doesn't
    bump and the new mission's recordings overwrite the prior one's m## prefix.
    """
    s = _fresh_session(
        current_mission="Mission_Acid",
        mission_index=5,
        last_mission_turn=4,
        disabled_actions=[
            {"weapon_id": "Brute_Sniper", "expires_turn": 999, "cause": "x"},
        ],
    )
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_Acid", "turn": 0}
    )
    assert changed is True
    assert s.mission_index == 6
    assert s.current_mission == "Mission_Acid"
    assert s.last_mission_turn == 0
    assert s.disabled_actions == []


def test_same_template_turn_progress_is_noop_but_tracks_high_water():
    """Normal turn-to-turn read on the same mission. Bridge turn advances;
    we update last_mission_turn in-place but return False (no structural
    change for the caller to save explicitly — cmd_read saves anyway)."""
    s = _fresh_session(
        current_mission="Mission_Acid",
        mission_index=5,
        last_mission_turn=2,
    )
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_Acid", "turn": 3}
    )
    assert changed is False
    assert s.mission_index == 5
    assert s.last_mission_turn == 3


def test_same_template_turn_zero_first_observation_is_noop():
    """Right after cmd_mission_end + new mission adopt, last_mission_turn=0
    and bridge.turn=0. No regression (0 < 0 is false), no bump.
    """
    s = _fresh_session(
        current_mission="Mission_Acid",
        mission_index=5,
        last_mission_turn=0,
    )
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_Acid", "turn": 0}
    )
    assert changed is False
    assert s.mission_index == 5
    assert s.last_mission_turn == 0


def test_first_mission_seeds_last_turn_from_bridge():
    """First adopt should snapshot the bridge turn as the high-water mark."""
    s = _fresh_session(current_mission="", mission_index=0,
                       last_mission_turn=-1)
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_BotDefense", "turn": 2}
    )
    assert changed is True
    assert s.current_mission == "Mission_BotDefense"
    assert s.mission_index == 0
    assert s.last_mission_turn == 2


def test_different_mission_id_resets_last_turn():
    s = _fresh_session(
        current_mission="Mission_BotDefense",
        mission_index=0,
        last_mission_turn=4,
    )
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_FreezeBots", "turn": 0}
    )
    assert changed is True
    assert s.mission_index == 1
    assert s.last_mission_turn == 0


def test_four_missions_with_repeating_template_get_unique_prefixes():
    """End-to-end: mission_index sequence 13 -> 14 -> 0 -> 1 (bridge view)
    must produce four unique session.mission_index values across an island
    boundary where the bridge re-zeroes its per-island counter AND the new
    island happens to start with a recurring template id (Mission_Acid).

    The bridge only emits ``mission_id`` (the template), so we synthesize
    the sequence as: Mission_Belt (turns 0..3) -> Mission_Final (turns 0..2)
    -> Mission_Acid (turns 0..2) -> Mission_Acid AGAIN, different instance
    (turns 0..2). The fourth mission shares the template name with the
    third — that's the volcano-final collision case.
    """
    s = _fresh_session(current_mission="", mission_index=0,
                       last_mission_turn=-1)

    # Mission 1: Mission_Belt, observe turns 0..3
    _auto_advance_mission(s, {"mission_id": "Mission_Belt", "turn": 0})
    for t in range(1, 4):
        _auto_advance_mission(s, {"mission_id": "Mission_Belt", "turn": t})
    assert s.mission_index == 0
    assert s.current_mission == "Mission_Belt"
    assert s.last_mission_turn == 3

    # Mission 2: Mission_Final, harness skipped cmd_mission_end. Different
    # template -> name-mismatch branch fires.
    _auto_advance_mission(s, {"mission_id": "Mission_Final", "turn": 0})
    for t in range(1, 3):
        _auto_advance_mission(s, {"mission_id": "Mission_Final", "turn": t})
    assert s.mission_index == 1
    assert s.current_mission == "Mission_Final"
    assert s.last_mission_turn == 2

    # Mission 3: Mission_Acid. Different template again -> bump.
    _auto_advance_mission(s, {"mission_id": "Mission_Acid", "turn": 0})
    for t in range(1, 3):
        _auto_advance_mission(s, {"mission_id": "Mission_Acid", "turn": t})
    assert s.mission_index == 2
    assert s.current_mission == "Mission_Acid"
    assert s.last_mission_turn == 2

    # Mission 4: Mission_Acid AGAIN, but it's a NEW instance on a new island
    # (bridge mission_id is just the template; we previously hit turn 2,
    # now bridge says turn 0 -> regression -> bump.)
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_Acid", "turn": 0}
    )
    assert changed is True
    assert s.mission_index == 3
    assert s.current_mission == "Mission_Acid"
    assert s.last_mission_turn == 0

    # Mission 4 ends fine, recordings would land at m03_*
    for t in range(1, 3):
        _auto_advance_mission(s, {"mission_id": "Mission_Acid", "turn": t})
    assert s.mission_index == 3
    assert s.last_mission_turn == 2

    # All four mission indices are unique.
    assert len({0, 1, 2, 3}) == 4


def test_session_round_trip_preserves_last_mission_turn():
    """last_mission_turn must round-trip through to_dict/from_dict so the
    high-water mark survives session reload between cmd_read invocations."""
    s = _fresh_session(
        current_mission="Mission_Acid",
        mission_index=5,
        last_mission_turn=3,
    )
    d = s.to_dict()
    assert d["last_mission_turn"] == 3
    s2 = RunSession.from_dict(d)
    assert s2.last_mission_turn == 3


def test_session_load_defaults_last_mission_turn_for_legacy_sessions():
    """A session.json written before this fix has no last_mission_turn key.
    Loading must default it to -1 (not crash, not 0 — 0 would falsely allow
    a turn-0 read to look like progress)."""
    # Synthesize a legacy session JSON dict (mission_index but no last_mission_turn).
    legacy = {
        "run_id": "legacy_run",
        "squad": "rift_walkers",
        "current_mission": "Mission_Acid",
        "mission_index": 5,
    }
    s = RunSession.from_dict(legacy)
    assert s.last_mission_turn == -1
    # And a same-template, turn=0 read on a legacy session must NOT bump
    # (no high-water mark to regress from).
    changed = _auto_advance_mission(
        s, {"mission_id": "Mission_Acid", "turn": 0}
    )
    assert changed is False
    assert s.mission_index == 5
