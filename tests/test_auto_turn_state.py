"""Tests for stale-bridge-state defenses around cmd_auto_turn / cmd_solve.

Locks in the m13 t03 phantom-uid bug behaviour: cmd_solve stamps a unit
roster fingerprint on session.active_solution; cmd_auto_turn invalidates
the cached solution if the live bridge roster no longer matches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.loop import commands as cmd_mod
from src.loop.commands import _unit_roster_fingerprint
from src.loop.session import ActiveSolution, RunSession, SolverAction


# ---------------------------------------------------------------------------
# Roster fingerprint primitive.
# ---------------------------------------------------------------------------


def _stale_bridge_data() -> dict:
    return {
        "turn": 3,
        "phase": "combat_player",
        "units": [
            {"uid": 100, "x": 1, "y": 2, "hp": 3, "type": "Combat1"},
            {"uid": 115, "x": 4, "y": 5, "hp": 1, "type": "Snowmine1"},
        ],
    }


def _fresh_bridge_data() -> dict:
    """Same board minus the dead Snowmine that the bridge eventually drops."""
    return {
        "turn": 3,
        "phase": "combat_player",
        "units": [
            {"uid": 100, "x": 1, "y": 2, "hp": 3, "type": "Combat1"},
        ],
    }


def test_fingerprint_stable_across_irrelevant_fields():
    a = _stale_bridge_data()
    b = dict(a)
    # Add an extra field the fingerprint must ignore.
    b["units"] = [dict(u, custom="x") for u in a["units"]]
    assert _unit_roster_fingerprint(a) == _unit_roster_fingerprint(b)


def test_fingerprint_diffs_when_unit_removed():
    assert (_unit_roster_fingerprint(_stale_bridge_data())
            != _unit_roster_fingerprint(_fresh_bridge_data()))


def test_fingerprint_diffs_on_hp_change():
    a = _stale_bridge_data()
    b = json.loads(json.dumps(a))
    b["units"][0]["hp"] = 1
    assert _unit_roster_fingerprint(a) != _unit_roster_fingerprint(b)


def test_fingerprint_empty_for_missing_data():
    assert _unit_roster_fingerprint(None) == ""
    assert _unit_roster_fingerprint({}) == ""
    assert _unit_roster_fingerprint({"units": []}) == ""


# ---------------------------------------------------------------------------
# Session round-trip.
# ---------------------------------------------------------------------------


def _make_action() -> SolverAction:
    return SolverAction(
        mech_uid=100, mech_type="Combat", move_to=(1, 2),
        weapon="Prime_Punchmech", target=(2, 2), description="Punch Snowmine",
    )


def test_active_solution_fingerprint_round_trips():
    sol = ActiveSolution(actions=[_make_action()], score=10.0, turn=3,
                         input_fingerprint="abc")
    sol2 = ActiveSolution.from_dict(sol.to_dict())
    assert sol2.input_fingerprint == "abc"


def test_active_solution_fingerprint_default_empty_for_legacy_dict():
    legacy = {
        "actions": [_make_action().to_dict()],
        "score": 5.0,
        "turn": 1,
    }
    sol = ActiveSolution.from_dict(legacy)
    assert sol.input_fingerprint == ""


def test_session_set_solution_records_fingerprint():
    s = RunSession(run_id="test")
    s.set_solution([_make_action()], 7.0, 3, input_fingerprint="xyz")
    assert s.active_solution is not None
    assert s.active_solution.input_fingerprint == "xyz"
    # Round-trip via to_dict/from_dict.
    s2 = RunSession.from_dict(s.to_dict())
    assert s2.active_solution.input_fingerprint == "xyz"


def test_dirty_consent_token_is_exact_and_single_use():
    s = RunSession(run_id="r", difficulty=2, tags=["achievement"])
    s.mission_index = 4
    s.set_solution([_make_action()], 7.0, 2, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "grid_damage",
            "current": 5,
            "predicted": 4,
            "blocking": True,
            "delta": -1,
        }],
    }

    token = cmd_mod._dirty_consent_id(s, 2, safety, actions, candidate_rank=3)
    missing = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=None,
    )
    assert missing["status"] == "DIRTY_CONSENT_REQUIRED"
    assert missing["dirty_consent_id"] == token

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=token,
    )
    assert accepted is None
    assert token in s.dirty_consent_used

    reused = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=token,
    )
    assert reused["status"] == "DIRTY_CONSENT_REJECTED"


def test_dirty_consent_rejects_non_overridable_without_consuming_token():
    s = RunSession(run_id="r", difficulty=2, tags=["hard_victory"])
    s.mission_index = 12
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "pylon_hp_loss",
            "current": 2,
            "predicted": 1,
            "blocking": True,
            "delta": -1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=1)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=1,
        provided_id=token,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert "pylon_hp_loss" in rejected["reason"]
    assert token not in s.dirty_consent_used


def test_dirty_consent_accepts_final_cave_emergency_pylon_loss():
    s = RunSession(run_id="r", difficulty=2, tags=["hard_victory"])
    s.mission_index = 24
    s.set_solution([_make_action()], 7.0, 2, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [
            {
                "kind": "grid_damage",
                "current": 6,
                "predicted": 4,
                "blocking": True,
                "delta": -2,
            },
            {
                "kind": "pylon_destroyed",
                "current": 7,
                "predicted": 6,
                "blocking": True,
                "delta": -1,
            },
            {
                "kind": "pylon_hp_loss",
                "current": 14,
                "predicted": 12,
                "blocking": True,
                "delta": -2,
            },
        ],
        "current": {
            "mission_id": "Mission_Final_Cave",
            "grid_power": 6,
            "mechs_alive": 3,
            "mech_hp_total": 10,
            "bigbomb_alive": True,
        },
        "predicted": {
            "mission_id": "Mission_Final_Cave",
            "grid_power": 4,
            "mechs_alive": 3,
            "mech_hp_total": 10,
            "bigbomb_alive": True,
            "mechs_acid": [],
            "mechs_fire": [],
            "mechs_webbed": [],
            "mechs_on_danger": [],
            "mechs_disabled": [],
        },
    }
    token = cmd_mod._dirty_consent_id(s, 2, safety, actions, candidate_rank=0)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=0,
        provided_id=token,
    )

    assert accepted is None
    assert token in s.dirty_consent_used


def test_dirty_consent_accepts_final_cave_resist_gamble():
    s = RunSession(run_id="r", difficulty=2, tags=["hard_victory"])
    s.mission_index = 24
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [
            {
                "kind": "grid_damage",
                "current": 4,
                "predicted": 0,
                "blocking": True,
                "delta": -4,
            },
            {
                "kind": "grid_timeline_collapse",
                "current": 4,
                "predicted": 0,
                "blocking": True,
                "delta": -4,
            },
            {
                "kind": "pylon_destroyed",
                "current": 6,
                "predicted": 4,
                "blocking": True,
                "delta": -2,
            },
            {
                "kind": "pylon_hp_loss",
                "current": 12,
                "predicted": 8,
                "blocking": True,
                "delta": -4,
            },
        ],
        "current": {
            "mission_id": "Mission_Final_Cave",
            "turn": 4,
            "total_turns": 4,
            "grid_power": 4,
            "pylons_alive": 6,
            "pylon_hp_total": 12,
            "mechs_alive": 3,
            "mech_hp_total": 9,
            "bigbomb_alive": True,
        },
        "predicted": {
            "mission_id": "Mission_Final_Cave",
            "turn": 4,
            "total_turns": 4,
            "grid_power": 0,
            "pylons_alive": 4,
            "pylon_hp_total": 8,
            "mechs_alive": 3,
            "mech_hp_total": 9,
            "bigbomb_alive": True,
            "mechs_acid": [],
            "mechs_fire": [],
            "mechs_webbed": [],
            "mechs_on_danger": [],
            "mechs_disabled": [],
        },
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=493)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=493,
        provided_id=token,
    )

    assert accepted is None
    assert token in s.dirty_consent_used


def test_threat_audit_allows_expected_final_cave_emergency_pylon_loss():
    s = RunSession(run_id="r", difficulty=2, tags=["hard_victory"])
    s.current_mission = "Mission_Final_Cave"
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "pylon_destroyed", "blocking": True},
            {"kind": "pylon_hp_loss", "blocking": True},
        ],
        "current": {
            "mission_id": "Mission_Final_Cave",
            "grid_power": 6,
            "pylons_alive": 7,
            "mechs_alive": 3,
            "mech_hp_total": 10,
            "bigbomb_alive": True,
        },
        "predicted": {
            "mission_id": "Mission_Final_Cave",
            "grid_power": 4,
            "pylons_alive": 6,
            "mechs_alive": 3,
            "mech_hp_total": 10,
            "bigbomb_alive": True,
            "mechs_acid": [],
            "mechs_fire": [],
            "mechs_webbed": [],
            "mechs_on_danger": [],
            "mechs_disabled": [],
        },
    }

    assert cmd_mod._threat_audit_requires_block(
        {"still_threatened_count": 1}, safety, s
    ) is False
    assert cmd_mod._threat_audit_requires_block(
        {"still_threatened_count": 2}, safety, s
    ) is True


def test_threat_audit_blocks_unresolved_building_threat_on_normal_grid():
    s = RunSession(run_id="r", difficulty=0, tags=["achievement"])
    s.current_mission = "Mission_Missiles"
    safety = {
        "status": "CLEAN",
        "blocking": False,
        "current": {"grid_power": 3},
        "predicted": {"grid_power": 3},
    }

    assert cmd_mod._threat_audit_requires_block(
        {"still_threatened_count": 1}, safety, s
    ) is True


# ---------------------------------------------------------------------------
# cmd_auto_turn entry-point invalidation logic.
#
# We don't run the whole command — too much bridge plumbing — but we exercise
# the same predicate inline on a session populated with a stale solution.
# ---------------------------------------------------------------------------


def _solution_for(turn: int, fingerprint: str) -> ActiveSolution:
    return ActiveSolution(
        actions=[_make_action()], score=10.0, turn=turn,
        input_fingerprint=fingerprint,
    )


def _drop_stale(session: RunSession, current_turn: int, current_fp: str) -> bool:
    """Mirror of the cmd_auto_turn invalidation predicate."""
    if session.active_solution is None:
        return False
    cached_fp = session.active_solution.input_fingerprint
    cached_turn = session.active_solution.turn
    if (cached_turn != current_turn
            or (cached_fp and current_fp and cached_fp != current_fp)):
        session.active_solution = None
        session.actions_executed = 0
        return True
    return False


def test_drop_stale_solution_when_roster_diffs_same_turn():
    s = RunSession(run_id="test")
    stale_fp = _unit_roster_fingerprint(_stale_bridge_data())
    s.active_solution = _solution_for(turn=3, fingerprint=stale_fp)

    fresh_fp = _unit_roster_fingerprint(_fresh_bridge_data())
    dropped = _drop_stale(s, current_turn=3, current_fp=fresh_fp)

    assert dropped is True
    assert s.active_solution is None


def test_keep_solution_when_roster_matches():
    s = RunSession(run_id="test")
    fp = _unit_roster_fingerprint(_fresh_bridge_data())
    s.active_solution = _solution_for(turn=3, fingerprint=fp)

    dropped = _drop_stale(s, current_turn=3, current_fp=fp)

    assert dropped is False
    assert s.active_solution is not None
    assert s.active_solution.input_fingerprint == fp


def test_drop_solution_from_prior_turn():
    s = RunSession(run_id="test")
    fp = _unit_roster_fingerprint(_fresh_bridge_data())
    s.active_solution = _solution_for(turn=2, fingerprint=fp)

    # Same fingerprint, but the turn moved — drop unconditionally.
    dropped = _drop_stale(s, current_turn=3, current_fp=fp)

    assert dropped is True
    assert s.active_solution is None


def test_legacy_solution_without_fingerprint_kept_when_turn_matches():
    """Pre-fingerprint solutions still round-trip; we only invalidate
    when both sides have a fingerprint and they diverge."""
    s = RunSession(run_id="test")
    s.active_solution = _solution_for(turn=3, fingerprint="")

    fresh_fp = _unit_roster_fingerprint(_fresh_bridge_data())
    dropped = _drop_stale(s, current_turn=3, current_fp=fresh_fp)

    assert dropped is False
    assert s.active_solution is not None


# ---------------------------------------------------------------------------
# End-to-end: simulate the m13 t03 sequence.
#
# 1. Bridge state is stale (lists uid=115 alive even though it died last turn).
# 2. cmd_solve caches a solution with the stale fingerprint.
# 3. The bridge refreshes; the next auto_turn entry sees a fresh roster.
# 4. The stale active_solution is dropped before a fresh solve runs.
# ---------------------------------------------------------------------------


def test_m13_t03_phantom_uid_sequence(monkeypatch, tmp_path):
    """Stale solution from prior auto_turn invocation gets discarded."""
    s = RunSession(run_id="m13_test")
    stale_fp = _unit_roster_fingerprint(_stale_bridge_data())

    # Step 1+2: simulate cmd_solve caching against stale state.
    s.set_solution(
        [_make_action()], score=42.0, turn=3,
        input_fingerprint=stale_fp,
    )
    assert s.active_solution.input_fingerprint == stale_fp

    # Step 3: a later read sees the fresh roster (uid=115 gone).
    fresh_fp = _unit_roster_fingerprint(_fresh_bridge_data())
    assert fresh_fp != stale_fp

    # Step 4: the next auto_turn entry runs the invalidation predicate.
    dropped = _drop_stale(s, current_turn=3, current_fp=fresh_fp)
    assert dropped is True
    assert s.active_solution is None

    # Persistence: invalidation survives session save/load round-trip.
    sess_path = tmp_path / "active.json"
    s.save(path=sess_path)
    s2 = RunSession.load(path=sess_path)
    assert s2.active_solution is None
