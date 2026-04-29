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
