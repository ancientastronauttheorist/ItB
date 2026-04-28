"""Fix #4 (2026-04-28): soft-disable threshold + per-run cap regression tests.

Background: a single run on 2026-04-28 had 3/3 squad weapons caged by the
auto-tuner because the threshold (`_SOFT_DISABLE_THRESHOLD = 2`) was so
loose that any wave of upstream sim drift took out the entire squad. The
fix tightens the threshold to 3 desyncs per signature AND caps the
simultaneously-disabled set at 2 weapons per run.

Tests here are pure-Python; no Rust rebuild needed.
"""

from __future__ import annotations

import pytest

from src.loop import weapon_penalty_log
from src.loop.commands import _maybe_soft_disable
from src.loop.session import RunSession
from src.solver import fuzzy_detector
from src.solver.verify import DiffResult


@pytest.fixture(autouse=True)
def _no_persistent_log(monkeypatch):
    """Stub weapon_penalty_log.record_soft_disable so tests don't write to
    the real data/weapon_penalty_log.json on disk."""
    monkeypatch.setattr(
        weapon_penalty_log, "record_soft_disable",
        lambda **kwargs: None,
    )


def _classification(top: str, model_gap: bool = False) -> dict:
    return {
        "top_category": top,
        "categories": [top],
        "subcategory": None,
        "model_gap": model_gap,
    }


def _ctx(weapon: str = "Prime_Shift", sub: str = "attack") -> dict:
    return {"weapon": weapon, "sub_action": sub}


# ── Threshold change (2 → 3) ─────────────────────────────────────────────────


def test_two_desyncs_do_not_soft_disable():
    """After two desyncs of weapon X within a run, no soft-disable fires."""
    prior = [{"signature": "push_dir|Prime_Shift|attack"}]
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=_ctx(), prior_events=prior,
    )
    assert sig["frequency"] == 1
    assert sig["proposed_tier"] == 4  # narrate, not cage


def test_three_desyncs_trigger_soft_disable():
    """After three desyncs of weapon X within a run, soft-disable fires."""
    prior = [
        {"signature": "push_dir|Prime_Shift|attack"},
        {"signature": "push_dir|Prime_Shift|attack"},
    ]
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=_ctx(), prior_events=prior,
    )
    assert sig["frequency"] == 2
    assert sig["proposed_tier"] == 2
    assert sig["confidence"] >= 0.8


def test_confidence_floor_satisfied_at_threshold():
    """Threshold=3 must produce conf ≥ floor (0.8) under the formula
    `0.5 + 0.1 * (freq+1)`. If a future formula tweak drops below the
    floor, _propose_response now downgrades to narrate — verify both
    ends of the contract here."""
    prior = [{"signature": "push_dir|Prime_Shift|attack"}] * 2
    sig = fuzzy_detector.evaluate(
        DiffResult(), _classification("push_dir"),
        context=_ctx(), prior_events=prior,
    )
    # 0.5 + 0.1 * 3 = 0.8 exactly.
    assert sig["confidence"] == 0.8


# ── Per-run cap (≤ 2 distinct disabled weapons) ──────────────────────────────


def _signal(weapon: str, freq: int = 2) -> dict:
    """Build a tier-2 signal as if `freq+1`-th desync just fired."""
    return {
        "proposed_tier": 2,
        "confidence": 0.8,
        "frequency": freq,
        "signature": f"push_dir|{weapon}|attack",
        "context": {"weapon": weapon, "sub_action": "attack"},
    }


def test_cap_blocks_third_distinct_weapon():
    """If 2 weapons are already disabled, the 3rd does not auto-disable
    even when the signal says tier 2. The narrator records it as
    skipped_by_cap so the user sees what was suppressed."""
    s = RunSession()
    fired: list[dict] = []
    _maybe_soft_disable(s, _signal("Brute_Grapple"), turn=1, fired=fired)
    _maybe_soft_disable(s, _signal("Prime_Shift"), turn=1, fired=fired)
    _maybe_soft_disable(s, _signal("Ranged_Artillerymech"), turn=1, fired=fired)

    # Only the first two land in disabled_actions.
    weapons_disabled = {e["weapon_id"] for e in s.disabled_actions}
    assert weapons_disabled == {"Brute_Grapple", "Prime_Shift"}
    # The third is logged in fired with skipped_by_cap=True.
    third = next(e for e in fired if e["weapon_id"] == "Ranged_Artillerymech")
    assert third.get("skipped_by_cap") is True
    assert third.get("new_entry") is False


def test_cap_does_not_block_re_flagging_existing_weapon():
    """The cap counts distinct weapons, not firings. Re-flagging a
    weapon already in the disabled set must extend its expiry and
    append the cause, never get blocked by the cap."""
    s = RunSession()
    fired: list[dict] = []
    _maybe_soft_disable(s, _signal("Brute_Grapple"), turn=1, fired=fired)
    _maybe_soft_disable(s, _signal("Prime_Shift"), turn=1, fired=fired)
    # Cap is now full. Re-flag Brute_Grapple — must succeed (extends expiry).
    _maybe_soft_disable(s, _signal("Brute_Grapple"), turn=2, fired=fired)
    weapons_disabled = {e["weapon_id"] for e in s.disabled_actions}
    assert weapons_disabled == {"Brute_Grapple", "Prime_Shift"}
    # Re-flag did NOT get marked skipped_by_cap.
    re_flag = fired[-1]
    assert re_flag["weapon_id"] == "Brute_Grapple"
    assert not re_flag.get("skipped_by_cap")


def test_cap_is_prospective_existing_entries_preserved():
    """If the cap is somehow already exceeded (e.g. a session loaded
    from disk pre-Fix-4 with 3 entries), the cap doesn't retroactively
    prune. New disables for already-listed weapons still extend expiry;
    new disables for novel weapons are blocked."""
    s = RunSession()
    # Simulate pre-Fix-4 state: 3 weapons already disabled.
    s.add_disabled_action("W1", "old_cause", expires_turn=10)
    s.add_disabled_action("W2", "old_cause", expires_turn=10)
    s.add_disabled_action("W3", "old_cause", expires_turn=10)
    assert len(s.disabled_actions) == 3

    fired: list[dict] = []
    # New attempt to disable W4 — blocked by cap.
    _maybe_soft_disable(s, _signal("W4"), turn=2, fired=fired)
    weapons = {e["weapon_id"] for e in s.disabled_actions}
    assert weapons == {"W1", "W2", "W3"}
    assert fired[-1].get("skipped_by_cap") is True


def test_cap_allows_first_two_disables():
    """Sanity: with no prior disables, the first two go through normally."""
    s = RunSession()
    fired: list[dict] = []
    _maybe_soft_disable(s, _signal("W1"), turn=1, fired=fired)
    _maybe_soft_disable(s, _signal("W2"), turn=1, fired=fired)
    assert len(s.disabled_actions) == 2
    assert all(not e.get("skipped_by_cap") for e in fired)
    assert all(e.get("new_entry") for e in fired)
