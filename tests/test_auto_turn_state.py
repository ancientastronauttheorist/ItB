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
from src.model.board import Board, Unit
from src.solver.verify import DiffResult


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


def test_pod_state_diff_queues_investigation(tmp_path, monkeypatch):
    monkeypatch.setattr(cmd_mod, "SNAPSHOT_DIR", tmp_path)
    diff = DiffResult(tile_diffs=[{
        "x": 5,
        "y": 4,
        "field": "has_pod",
        "predicted": True,
        "actual": False,
    }])
    investigations = []

    cmd_mod._maybe_flag_pod_state_diff(
        investigations,
        diff,
        {"categories": ["pod"], "top_category": "pod"},
        {"tiles": []},
        Board(),
        {
            "sub_action": "attack",
            "action_index": 2,
            "mech_uid": 7,
            "weapon": "Science_Swap",
            "target": [5, 3],
        },
        run_id="run",
        turn=2,
        failure_db_id="failure",
    )

    assert len(investigations) == 1
    inv = investigations[0]
    assert inv["kind"] == "pod_state_diff"
    assert inv["pod_diffs"][0]["field"] == "has_pod"
    context = json.loads((Path(inv["snapshot_path"]) / "context.json").read_text())
    assert context["kind"] == "pod_state_diff"
    assert context["weapon"] == "Science_Swap"


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
    assert not cmd_mod.plan_requires_safety_block(
        safety,
        allow_dirty_plan=True,
        allow_kill_limit_objective_dirty=(
            cmd_mod._allow_kill_limit_objective_dirty_consent(s)
        ),
    )

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


def test_dirty_consent_rejects_mech_loss_without_consuming_token():
    s = RunSession(run_id="r", difficulty=0, tags=["achievement"])
    s.achievement_targets = ["Lightning War"]
    s.mission_index = 3
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "mech_lost",
            "current": 3,
            "predicted": 2,
            "blocking": True,
            "delta": -1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=0)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=0,
        provided_id=token,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert "mech_lost" in rejected["reason"]
    assert token not in s.dirty_consent_used


def test_dirty_consent_accepts_mech_loss_with_stress_flag():
    s = RunSession(run_id="r", difficulty=3, tags=["solver_eval"])
    s.mission_index = 1
    s.set_solution([_make_action()], 7.0, 3, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "mech_lost",
            "current": 3,
            "predicted": 2,
            "blocking": True,
            "delta": -1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 3, safety, actions, candidate_rank=3)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=3,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=token,
        allow_mech_loss=True,
    )

    assert accepted is None
    assert token in s.dirty_consent_used


def test_dirty_consent_accepts_protected_objective_loss_with_stress_flag():
    s = RunSession(run_id="r", difficulty=3, tags=["solver_eval"])
    s.mission_index = 3
    s.set_solution([_make_action()], 7.0, 2, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "protected_objective_unit_lost",
            "current": 2,
            "predicted": 1,
            "blocking": True,
            "delta": -1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 2, safety, actions, candidate_rank=200)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=200,
        provided_id=token,
    )
    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=200,
        provided_id=token,
        allow_protected_objective_loss=True,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert accepted is None
    assert token in s.dirty_consent_used


def test_dirty_consent_accepts_objective_loss_with_stress_flag():
    s = RunSession(run_id="r", difficulty=3, tags=["solver_eval"])
    s.mission_index = 3
    s.set_solution([_make_action()], 7.0, 2, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [
            {
                "kind": "objective_building_destroyed",
                "current": 1,
                "predicted": 0,
                "blocking": True,
                "delta": -1,
            },
            {
                "kind": "objective_building_hp_loss",
                "current": 1,
                "predicted": 0,
                "blocking": True,
                "delta": -1,
            },
            {
                "kind": "protected_objective_unit_lost",
                "current": 1,
                "predicted": 0,
                "blocking": True,
                "delta": -1,
            },
        ],
    }
    token = cmd_mod._dirty_consent_id(s, 2, safety, actions, candidate_rank=0)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=0,
        provided_id=token,
    )
    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=0,
        provided_id=token,
        allow_objective_loss=True,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert "objective_building_destroyed" in rejected["reason"]
    assert accepted is None
    assert token in s.dirty_consent_used


def test_dirty_consent_validation_can_delay_token_consumption():
    s = RunSession(run_id="r", difficulty=0, tags=["achievement"])
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

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=token,
        consume=False,
    )

    assert accepted is None
    assert token not in s.dirty_consent_used


def test_dirty_consent_progress_mark_consumes_delayed_token(monkeypatch):
    s = RunSession(run_id="r", difficulty=0, tags=["achievement"])
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
    saves = []
    monkeypatch.setattr(s, "save", lambda: saves.append(list(s.dirty_consent_used)))

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=2,
        plan_safety=safety,
        actions=actions,
        candidate_rank=3,
        provided_id=token,
        consume=False,
    )

    assert accepted is None
    assert token not in s.dirty_consent_used
    assert cmd_mod._dirty_consent_mark_used(s, token) is True
    assert token in s.dirty_consent_used
    assert saves == [[token]]
    assert cmd_mod._dirty_consent_mark_used(s, token) is False
    assert saves == [[token]]


def test_dirty_consent_accepts_kill_limit_failure_for_non_perfect_targets():
    s = RunSession(
        run_id="r",
        difficulty=0,
        tags=["achievement"],
        achievement_targets=["Quantum Entanglement", "This is Fine"],
    )
    s.mission_index = 7
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "kill_limit_objective_failed",
            "current": 4,
            "predicted": 6,
            "blocking": True,
            "delta": 2,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=23)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=23,
        provided_id=token,
    )

    assert accepted is None
    assert token in s.dirty_consent_used


def test_dirty_consent_accepts_kill_count_failure_for_non_perfect_targets():
    s = RunSession(
        run_id="r",
        difficulty=0,
        tags=["achievement"],
        achievement_targets=["Healing"],
    )
    s.mission_index = 9
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "kill_objective_failed",
            "current": 2,
            "predicted": 3,
            "blocking": True,
            "delta": 1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=8)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=8,
        provided_id=token,
    )

    assert accepted is None
    assert token in s.dirty_consent_used


@pytest.mark.parametrize(
    ("targets", "tags"),
    [
        (["There is No Try"], ["achievement"]),
        (["Perfect Strategy"], ["achievement"]),
        (["Quantum Entanglement"], ["perfect_strategy"]),
    ],
)
def test_dirty_consent_rejects_kill_limit_failure_for_perfect_targets(
    targets, tags
):
    s = RunSession(
        run_id="r",
        difficulty=0,
        tags=tags,
        achievement_targets=targets,
    )
    s.mission_index = 7
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "kill_limit_objective_failed",
            "current": 4,
            "predicted": 6,
            "blocking": True,
            "delta": 2,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=23)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=23,
        provided_id=token,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert "kill_limit_objective_failed" in rejected["reason"]
    assert token not in s.dirty_consent_used


def test_dirty_consent_rejects_kill_count_failure_for_perfect_targets():
    s = RunSession(
        run_id="r",
        difficulty=0,
        tags=["achievement"],
        achievement_targets=["Perfect Strategy"],
    )
    s.mission_index = 9
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{
            "kind": "kill_objective_failed",
            "current": 2,
            "predicted": 3,
            "blocking": True,
            "delta": 1,
        }],
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=8)

    rejected = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=8,
        provided_id=token,
    )

    assert rejected["status"] == "DIRTY_CONSENT_REJECTED"
    assert "kill_objective_failed" in rejected["reason"]
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


def test_dirty_consent_accepts_final_bomb_bonus_building_loss():
    s = RunSession(run_id="r", difficulty=0, tags=["achievement_hunt"])
    s.mission_index = 5
    s.set_solution([_make_action()], 7.0, 4, input_fingerprint="fp")
    actions = s.active_solution.actions
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [
            {
                "kind": "grid_damage",
                "current": 7,
                "predicted": 6,
                "blocking": True,
                "delta": -1,
            },
            {
                "kind": "objective_building_destroyed",
                "current": 1,
                "predicted": 0,
                "blocking": True,
                "delta": -1,
            },
            {
                "kind": "objective_building_hp_loss",
                "current": 1,
                "predicted": 0,
                "blocking": True,
                "delta": -1,
            },
        ],
        "current": {
            "mission_id": "Mission_Bomb",
            "turn": 4,
            "total_turns": 4,
            "grid_power": 7,
            "protected_objective_units_alive": 2,
            "mechs_alive": 3,
        },
        "predicted": {
            "mission_id": "Mission_Bomb",
            "turn": 4,
            "total_turns": 4,
            "grid_power": 6,
            "protected_objective_units_alive": 2,
            "mechs_alive": 3,
            "mechs_acid": [],
            "mechs_fire": [],
            "mechs_webbed": [],
            "mechs_on_danger": [],
            "mechs_disabled": [],
        },
    }
    token = cmd_mod._dirty_consent_id(s, 4, safety, actions, candidate_rank=36)

    accepted = cmd_mod._dirty_consent_gate(
        s,
        turn=4,
        plan_safety=safety,
        actions=actions,
        candidate_rank=36,
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


def test_partial_re_solve_blocks_before_spending_uncovered_threat_plan():
    s = RunSession(run_id="r", difficulty=0, tags=["achievement"])
    safety = {
        "status": "CLEAN",
        "blocking": False,
        "current": {"grid_power": 5},
        "predicted": {"grid_power": 5},
    }
    action = SolverAction(
        mech_uid=0,
        mech_type="NeedleMech",
        move_to=(6, 5),
        weapon="Brute_KickBack",
        target=(4, 5),
        description="NeedleMech, move C4->C2, fire Reverse Thrusters at C4",
    )

    result = cmd_mod._partial_re_solve_threat_block_result(
        threat_audit={
            "status": "WARN",
            "still_threatened_count": 1,
            "entries": [{
                "target_visual": "A6",
                "coverage": {"reason": "still_threatened_current"},
            }],
        },
        plan_safety=safety,
        session=s,
        turn=4,
        actions_completed=2,
        re_solve_count=1,
        actions=[action],
        desync={"phase": "attack", "action_index": 1, "mech_uid": 1},
    )

    assert result is not None
    assert result["status"] == "THREAT_AUDIT_BLOCKED_RE_SOLVE"
    assert result["actions"] == [action.description]
    assert "Do not spend remaining actions" in result["next_step"]


def _projected_threat_board(*, queued: bool) -> dict:
    enemy = {
        "uid": 10,
        "type": "Firefly1",
        "x": 4,
        "y": 4,
        "hp": 3,
        "max_hp": 3,
        "team": 6,
        "weapons": ["FireflyAtk1"],
        "active": False,
        "has_queued_attack": queued,
    }
    if queued:
        enemy["queued_target"] = [4, 2]
        enemy["queued_origin"] = [4, 4]
    return {
        "turn": 1,
        "grid_power": 5,
        "grid_power_max": 7,
        "tiles": [{
            "x": 4,
            "y": 2,
            "terrain": "building",
            "building_hp": 1,
        }],
        "units": [enemy],
    }


def test_partial_re_solve_threat_audit_ignores_next_turn_requeues():
    post_player = _projected_threat_board(queued=False)
    post_enemy = _projected_threat_board(queued=True)
    post_enemy["turn"] = 2

    audit = cmd_mod._audit_projected_post_player_threats(
        {
            "post_player_board": post_player,
            "final_board": post_enemy,
        },
        {},
        [],
    )

    assert audit["status"] == "OK"
    assert audit["current_threat_count"] == 0
    assert audit["phase"] == "predicted_partial_re_solve_post_player"
    assert cmd_mod._partial_re_solve_threat_block_result(
        threat_audit=audit,
        plan_safety={
            "status": "CLEAN",
            "blocking": False,
            "current": {"grid_power": 5},
            "predicted": {"grid_power": 5},
        },
        session=RunSession(run_id="r"),
        turn=1,
        actions_completed=1,
        re_solve_count=1,
        actions=[],
        desync={},
    ) is None


def test_partial_re_solve_threat_audit_keeps_real_post_player_threats():
    post_player = _projected_threat_board(queued=True)
    audit = cmd_mod._audit_projected_post_player_threats(
        {"post_player_board": post_player},
        {},
        [],
    )

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    result = cmd_mod._partial_re_solve_threat_block_result(
        threat_audit=audit,
        plan_safety={
            "status": "CLEAN",
            "blocking": False,
            "current": {"grid_power": 5},
            "predicted": {"grid_power": 5},
        },
        session=RunSession(run_id="r"),
        turn=1,
        actions_completed=1,
        re_solve_count=1,
        actions=[],
        desync={},
    )
    assert result is not None
    assert result["status"] == "THREAT_AUDIT_BLOCKED_RE_SOLVE"


def test_partial_re_solve_record_preserves_final_board(monkeypatch):
    import itb_solver

    bridge_data = {
        "phase": "combat_player",
        "turn": 1,
        "total_turns": 4,
        "remaining_spawns": 0,
        "grid_power": 5,
        "grid_power_max": 7,
        "spawning_tiles": [],
        "tiles": [],
        "units": [{
            "uid": 0,
            "type": "PunchMech",
            "mech": True,
            "team": 1,
            "x": 4,
            "y": 4,
            "hp": 3,
            "max_hp": 3,
            "active": True,
            "can_move": True,
            "weapons": ["Prime_Punchmech"],
        }],
    }
    post_player = json.loads(json.dumps(bridge_data))
    post_player["units"][0]["active"] = False
    final_board = json.loads(json.dumps(post_player))
    final_board["turn"] = 2

    def fake_solve(_payload, _time_limit):
        return json.dumps({
            "actions": [{
                "mech_uid": 0,
                "mech_type": "PunchMech",
                "move_to": [4, 4],
                "weapon_id": "None",
                "target": [255, 255],
                "description": "PunchMech, skip",
            }],
            "score": 0,
            "stats": {
                "timed_out": False,
                "permutations_tried": 1,
                "total_permutations": 1,
            },
            "threats": [],
            "initial_building_threats": [],
        })

    final_summary = cmd_mod._capture_board_summary(
        Board.from_bridge_data(final_board),
        final_board,
    )

    def fake_replay(*_args, **_kwargs):
        return {
            "action_results": [{}],
            "predicted_states": [],
            "post_player_board": post_player,
            "final_board": final_board,
            "predicted_outcome": final_summary,
            "score_breakdown": {},
            "replay_annotations": [],
        }

    monkeypatch.setattr(itb_solver, "solve", fake_solve)
    monkeypatch.setattr("src.solver.solver.replay_solution", fake_replay)
    monkeypatch.setattr(
        cmd_mod,
        "_enrich_bridge_mech_weapons_from_save",
        lambda _data: [],
    )
    monkeypatch.setattr(
        cmd_mod,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda _data: [],
    )

    _actions, _states, _score, _safety, solve_data = (
        cmd_mod._re_solve_partial(
            Board.from_bridge_data(bridge_data),
            bridge_data,
            done_uids=set(),
            mid_action_uid=None,
            time_limit=1.0,
            session=RunSession(run_id="run"),
        )
    )

    assert solve_data is not None
    assert solve_data["partial_re_solve"] == {
        "done_uids": [],
        "mid_action_uid": None,
    }
    assert solve_data["final_board"] == final_board


def test_enemy_survived_fuzzy_blocks_end_turn_even_when_audit_clean():
    block = cmd_mod._fuzzy_detections_require_end_turn_block([{
        "signature": "death|Brute_Grapple|attack",
        "asymmetry": ["enemy_survived_unexpectedly"],
        "confidence": 0.8,
        "proposed_tier": 2,
        "context": {
            "weapon": "Brute_Grapple",
            "action_index": 2,
        },
    }])

    assert block == {
        "reason": "enemy_survived_unexpectedly",
        "signature": "death|Brute_Grapple|attack",
        "weapon": "Brute_Grapple",
        "action_index": 2,
        "confidence": 0.8,
        "proposed_tier": 2,
    }


def test_benign_fuzzy_does_not_block_end_turn():
    assert cmd_mod._fuzzy_detections_require_end_turn_block([{
        "signature": "status|Prime_Lightning|attack",
        "asymmetry": [],
        "context": {"weapon": "Prime_Lightning"},
    }]) is None


def test_burrower_missing_after_damage_drift_is_harmless_for_re_solve():
    diff = DiffResult(unit_diffs=[{
        "uid": 30,
        "type": "Burrower1",
        "field": "missing_in_actual",
        "predicted": "present",
        "actual": "absent",
    }])

    assert cmd_mod._is_harmless_burrower_missing_drift(diff) is True


def test_burrower_missing_drift_does_not_hide_mixed_losses():
    diff = DiffResult(
        unit_diffs=[{
            "uid": 30,
            "type": "Burrower1",
            "field": "missing_in_actual",
            "predicted": "present",
            "actual": "absent",
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 5,
            "actual": 4,
        }],
    )

    assert cmd_mod._is_harmless_burrower_missing_drift(diff) is False


def test_non_burrower_missing_still_requires_re_solve():
    diff = DiffResult(unit_diffs=[{
        "uid": 8,
        "type": "Bouncer1",
        "field": "missing_in_actual",
        "predicted": "present",
        "actual": "absent",
    }])

    assert cmd_mod._is_harmless_burrower_missing_drift(diff) is False


def test_predicted_spider_psion_egg_missing_during_attack_gets_settle_retry():
    diff = DiffResult(unit_diffs=[{
        "uid": 628,
        "type": "SpiderlingEgg1",
        "field": "missing_in_actual",
        "predicted": "present",
        "actual": "absent",
    }])

    assert cmd_mod._is_transient_delayed_spider_psion_egg_diff(
        diff, "attack"
    ) is True


def test_unexpected_spider_psion_egg_or_mixed_loss_does_not_retry():
    unexpected = DiffResult(unit_diffs=[{
        "uid": 628,
        "type": "SpiderlingEgg1",
        "field": "missing_in_predicted",
        "predicted": "absent",
        "actual": "present",
    }])
    mixed = DiffResult(
        unit_diffs=[{
            "uid": 628,
            "type": "SpiderlingEgg1",
            "field": "missing_in_actual",
            "predicted": "present",
            "actual": "absent",
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 4,
            "actual": 3,
        }],
    )
    other_egg = DiffResult(unit_diffs=[{
        "uid": 629,
        "type": "SpiderlingEgg2",
        "field": "missing_in_actual",
        "predicted": "present",
        "actual": "absent",
    }])

    assert cmd_mod._is_transient_delayed_spider_psion_egg_diff(
        unexpected, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_spider_psion_egg_diff(
        mixed, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_spider_psion_egg_diff(
        other_egg, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_spider_psion_egg_diff(
        other_egg, "move"
    ) is False


def test_delayed_acid_pool_retries_only_predicted_pool_lag():
    delayed = DiffResult(tile_diffs=[{
        "x": 4,
        "y": 4,
        "field": "acid",
        "predicted": True,
        "actual": False,
    }])
    inverse = DiffResult(tile_diffs=[{
        "x": 4,
        "y": 4,
        "field": "acid",
        "predicted": False,
        "actual": True,
    }])
    mixed = DiffResult(
        tile_diffs=list(delayed.tile_diffs),
        unit_diffs=[{
            "uid": 1,
            "field": "hp",
            "predicted": 3,
            "actual": 4,
        }],
    )

    assert cmd_mod._is_transient_delayed_acid_pool_diff(
        delayed, "attack"
    ) is True
    assert cmd_mod._is_transient_delayed_acid_pool_diff(
        delayed, "move"
    ) is False
    assert cmd_mod._is_transient_delayed_acid_pool_diff(
        inverse, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_acid_pool_diff(
        mixed, "attack"
    ) is False


def _delayed_chained_bombrock_building_case(
    *,
    predicted_hp: int = 1,
    actual_hp: int = 2,
    building: tuple[int, int] = (5, 1),
    second_rock: tuple[int, int] = (4, 1),
):
    predicted = {
        "units": [
            {
                "uid": 868,
                "type": "BombRock",
                "pos": [4, 2],
                "hp": 0,
                "alive": False,
            },
            {
                "uid": 869,
                "type": "BombRock",
                "pos": list(second_rock),
                "hp": 0,
                "alive": False,
            },
        ],
    }
    diff = DiffResult(tile_diffs=[{
        "x": building[0],
        "y": building[1],
        "field": "building_hp",
        "predicted": predicted_hp,
        "actual": actual_hp,
    }])
    return diff, predicted


def test_delayed_chained_bombrock_building_damage_gets_settle_retry():
    # Chaos Roll Unfair run 20260713_052159_731, Mission_DungBoss turn 1:
    # Ignite pushed the F4 BombRock into G4.  The first bridge read had
    # removed both rocks but had not yet applied G4's blast to G3.
    diff, predicted = _delayed_chained_bombrock_building_case()

    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        diff, predicted, "attack"
    ) is True


def test_chained_bombrock_retry_rejects_inverse_or_unproven_geometry():
    inverse, predicted = _delayed_chained_bombrock_building_case(
        predicted_hp=2, actual_hp=1
    )
    off_blast, _ = _delayed_chained_bombrock_building_case(building=(6, 6))
    single_rock, single_predicted = _delayed_chained_bombrock_building_case(
        second_rock=(1, 1)
    )
    alive_rock, alive_predicted = _delayed_chained_bombrock_building_case()
    alive_predicted["units"][1].update({"hp": 1, "alive": True})

    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        inverse, predicted, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        off_blast, predicted, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        single_rock, single_predicted, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        alive_rock, alive_predicted, "attack"
    ) is False


def test_chained_bombrock_retry_rejects_mixed_loss_or_wrong_phase():
    mixed, predicted = _delayed_chained_bombrock_building_case()
    mixed.scalar_diffs.append({
        "field": "grid_power",
        "predicted": 7,
        "actual": 6,
    })
    mixed_unit, _ = _delayed_chained_bombrock_building_case()
    mixed_unit.unit_diffs.append({
        "uid": 838,
        "type": "DungBoss",
        "field": "hp",
        "predicted": 4,
        "actual": 5,
    })
    clean_shape, _ = _delayed_chained_bombrock_building_case()

    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        mixed, predicted, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        mixed_unit, predicted, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_chained_bombrock_building_diff(
        clean_shape, predicted, "move"
    ) is False


def test_chained_bombrock_retry_uses_newer_nontransient_reread():
    initial, predicted = _delayed_chained_bombrock_building_case()
    inverse, _ = _delayed_chained_bombrock_building_case(
        predicted_hp=1, actual_hp=0
    )

    assert cmd_mod._delayed_chained_bombrock_reread_became_nontransient(
        initial, inverse, predicted, "attack"
    ) is True


def _delayed_terrain_death_case(
    *,
    terrain: str = "water",
    flying: bool = False,
    massive: bool = False,
    frozen: bool = False,
):
    uid = 638
    board = Board()
    board.tile(6, 2).terrain = terrain
    board.units.append(Unit(
        uid=uid,
        type="Scorpion1",
        x=6,
        y=2,
        hp=2,
        max_hp=3,
        team=6,
        is_mech=False,
        move_speed=3,
        flying=flying,
        massive=massive,
        armor=True,
        pushable=True,
        weapon="ScorpionAtk1",
        frozen=frozen,
        shield=True,
    ))
    predicted = {
        "units": [{
            "uid": uid,
            "type": "Scorpion1",
            "pos": [6, 2],
            "hp": 0,
            "alive": False,
            "status": {
                "frozen": frozen,
                "shield": True,
            },
        }],
    }
    diff = DiffResult(unit_diffs=[{
        "uid": uid,
        "type": "Scorpion1",
        "field": "alive",
        "predicted": False,
        "actual": True,
    }])
    return diff, predicted, board


def test_delayed_pushed_enemy_water_death_gets_settle_retry():
    # Chaos Unfair run 20260712_193021_862, Mission_Belt turn 2:
    # Ranged_Rocket pushed Scorpion uid638 onto Water.  The command's first
    # verify read saw the Vek alive on its lethal landing tile; a later read
    # showed the replay-predicted death.  Armor and Shield do not prevent the
    # terrain kill, so their presence must not suppress this narrow retry.
    diff, predicted, board = _delayed_terrain_death_case()

    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        diff, predicted, board, "attack"
    ) is True


def test_verified_building_shield_shadow_requires_shield_only_diff(monkeypatch):
    promoted = []
    monkeypatch.setattr(
        cmd_mod,
        "update_building_shield_ledger_from_verified_snapshot",
        lambda predicted, board, data: promoted.append((predicted, board, data)) or True,
    )
    predicted = {"tiles_changed": []}
    board = Board()
    data = {"tile_shield_ledger_known": True}
    shield_only = DiffResult(tile_diffs=[{
        "x": 4,
        "y": 3,
        "field": "shield",
        "predicted": False,
        "actual": True,
    }])

    assert cmd_mod._reconcile_verified_building_shield_shadow(
        shield_only, predicted, board, data
    ) is True
    assert promoted == [(predicted, board, data)]

    mixed = DiffResult(
        tile_diffs=shield_only.tile_diffs,
        unit_diffs=[{
            "uid": 638,
            "type": "Scorpion1",
            "field": "hp",
            "predicted": 0,
            "actual": 1,
        }],
    )
    assert cmd_mod._reconcile_verified_building_shield_shadow(
        mixed, predicted, board, data
    ) is False
    assert promoted == [(predicted, board, data)]


def test_delayed_terrain_death_retry_matches_flight_and_massive_rules():
    frozen_flyer = _delayed_terrain_death_case(flying=True, frozen=True)
    massive_chasm = _delayed_terrain_death_case(
        terrain="chasm", massive=True
    )
    live_flyer = _delayed_terrain_death_case(flying=True)
    massive_water = _delayed_terrain_death_case(massive=True)
    frozen_ground_water = _delayed_terrain_death_case(frozen=True)

    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        *frozen_flyer, "attack"
    ) is True
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        *massive_chasm, "attack"
    ) is True
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        *live_flyer, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        *massive_water, "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        *frozen_ground_water, "attack"
    ) is False


def test_delayed_terrain_death_retry_rejects_unrelated_or_nonlethal_diffs():
    diff, predicted, board = _delayed_terrain_death_case(terrain="ground")
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        diff, predicted, board, "attack"
    ) is False

    board.tile(6, 2).terrain = "water"
    diff.scalar_diffs.append({
        "field": "grid_power",
        "predicted": 4,
        "actual": 3,
    })
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        diff, predicted, board, "attack"
    ) is False
    diff.scalar_diffs.clear()
    assert cmd_mod._is_transient_delayed_lethal_terrain_death_diff(
        diff, predicted, board, "move"
    ) is False


def test_tri_rocket_enemy_damage_only_diff_gets_settle_retry():
    diff = DiffResult(unit_diffs=[
        {
            "uid": 96,
            "type": "Scorpion1",
            "field": "hp",
            "predicted": 3,
            "actual": 4,
        },
        {
            "uid": 95,
            "type": "Jelly_Health1",
            "field": "alive",
            "predicted": False,
            "actual": True,
        },
    ])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Tri-Rocket", "attack"
    ) is True


def test_tri_rocket_settle_retry_rejects_mixed_grid_loss():
    diff = DiffResult(
        unit_diffs=[{
            "uid": 96,
            "type": "Scorpion1",
            "field": "hp",
            "predicted": 3,
            "actual": 4,
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 5,
            "actual": 4,
        }],
    )

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Ranged_Crack", "attack"
    ) is False


def test_missile_barrage_enemy_damage_only_diff_gets_settle_retry():
    # Chaos Unfair run 20260712_193021_862, Mission_Missiles turn 1:
    # player-unit missiles had landed when the first verify read arrived, but
    # five enemy missiles were still in flight. The settled board matched the
    # replay prediction exactly.
    diff = DiffResult(unit_diffs=[
        {
            "uid": uid,
            "type": unit_type,
            "field": "hp",
            "predicted": predicted,
            "actual": predicted + 1,
        }
        for uid, unit_type, predicted in [
            (610, "Scorpion1", 2),
            (611, "Bouncer2", 3),
            (613, "Firefly1", 2),
            (614, "Firefly2", 4),
            (615, "Bouncer1", 2),
        ]
    ])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missiles_OneDmg", "attack"
    ) is True


def test_missile_barrage_player_damage_lag_gets_settle_retry():
    diff = DiffResult(unit_diffs=[{
        "uid": 1,
        "type": "RockartMech",
        "field": "hp",
        "predicted": 1,
        "actual": 2,
    }])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missile Barrage", "attack"
    ) is True


def test_missile_barrage_mixed_shield_consumption_and_damage_lag_retries():
    # Same run, turn 3: the Bouncer's shield-consumption missile and the
    # Spider Psion's damage missile were both still airborne at first read.
    diff = DiffResult(unit_diffs=[
        {
            "uid": 615,
            "type": "Bouncer1",
            "field": "status.shield",
            "predicted": False,
            "actual": True,
        },
        {
            "uid": 623,
            "type": "Jelly_Spider1",
            "field": "hp",
            "predicted": 1,
            "actual": 2,
        },
    ])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missiles_OneDmg", "attack"
    ) is True


def test_missile_barrage_delayed_acid_death_splash_tiles_get_settle_retry():
    # Chaos Roll Unfair run 20260713_052159_731, Mission_Missiles turn 1:
    # Firefly2 was already absent at the first read, while its ACID corpse pool
    # and Blast-Psion splash on the adjacent Mountain were still landing.  A
    # later Spider missile was also in flight.  The settled board matched the
    # replay prediction exactly.
    diff = DiffResult(
        unit_diffs=[{
            "uid": 1332,
            "type": "Spider2",
            "field": "hp",
            "predicted": 2,
            "actual": 3,
        }],
        tile_diffs=[
            {
                "x": 5,
                "y": 1,
                "field": "terrain",
                "predicted": "rubble",
                "actual": "mountain",
            },
            {
                "x": 5,
                "y": 1,
                "field": "building_hp",
                "predicted": 0,
                "actual": 1,
                "predicted_terrain": "rubble",
                "actual_terrain": "mountain",
            },
            {
                "x": 5,
                "y": 2,
                "field": "acid",
                "predicted": True,
                "actual": False,
            },
        ],
    )

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missiles_OneDmg", "attack"
    ) is True
    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missile Barrage", "attack"
    ) is True


def test_missile_barrage_tile_retry_rejects_unpaired_or_inverse_diffs():
    cases = (
        DiffResult(tile_diffs=[{
            "x": 5,
            "y": 1,
            "field": "terrain",
            "predicted": "rubble",
            "actual": "mountain",
        }]),
        DiffResult(tile_diffs=[
            {
                "x": 5,
                "y": 1,
                "field": "terrain",
                "predicted": "mountain",
                "actual": "rubble",
            },
            {
                "x": 5,
                "y": 1,
                "field": "building_hp",
                "predicted": 1,
                "actual": 0,
                "predicted_terrain": "mountain",
                "actual_terrain": "rubble",
            },
        ]),
        DiffResult(tile_diffs=[{
            "x": 5,
            "y": 2,
            "field": "acid",
            "predicted": False,
            "actual": True,
        }]),
        DiffResult(tile_diffs=[{
            "x": 5,
            "y": 2,
            "field": "smoke",
            "predicted": True,
            "actual": False,
        }]),
    )

    for diff in cases:
        assert cmd_mod._is_transient_delayed_multihit_damage_diff(
            diff, "Missiles_OneDmg", "attack"
        ) is False


def test_shield_barrage_status_lag_gets_longer_settle_retry():
    diff = DiffResult(unit_diffs=[
        {
            "uid": 1,
            "type": "RockartMech",
            "field": "status.shield",
            "predicted": True,
            "actual": False,
        },
        {
            "uid": 610,
            "type": "Scorpion1",
            "field": "status.shield",
            "predicted": True,
            "actual": False,
        },
    ])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Missiles_Shield", "attack"
    ) is True


def test_missile_barrage_settle_retry_rejects_source_or_scalar_diff():
    source_diff = DiffResult(unit_diffs=[{
        "uid": 608,
        "type": "Missile_Unit",
        "field": "hp",
        "predicted": 1,
        "actual": 2,
    }])
    mixed_diff = DiffResult(
        unit_diffs=[{
            "uid": 610,
            "type": "Scorpion1",
            "field": "hp",
            "predicted": 2,
            "actual": 3,
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 5,
            "actual": 4,
        }],
    )

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        source_diff, "Missiles_OneDmg", "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        mixed_diff, "Missiles_OneDmg", "attack"
    ) is False

    shield_source_diff = DiffResult(unit_diffs=[{
        "uid": 608,
        "type": "Missile_Unit",
        "field": "status.shield",
        "predicted": True,
        "actual": False,
    }])
    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        shield_source_diff, "Missiles_Shield", "attack"
    ) is False


def test_prime_leap_delayed_blast_building_damage_gets_settle_retry():
    diff = DiffResult(tile_diffs=[{
        "x": 5,
        "y": 2,
        "field": "building_hp",
        "predicted": 1,
        "actual": 2,
    }])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Prime_Leap", "attack"
    ) is True


def test_prime_leap_delayed_push_position_gets_settle_retry():
    diff = DiffResult(unit_diffs=[{
        "uid": 364,
        "type": "Jelly_Explode1",
        "field": "pos",
        "predicted": [7, 3],
        "actual": [6, 3],
    }])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Prime_Leap", "attack"
    ) is True
    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Prime_Leap_AB", "attack"
    ) is True


def test_prime_leap_push_settle_retry_rejects_mixed_status_diff():
    diff = DiffResult(unit_diffs=[
        {
            "uid": 364,
            "type": "Jelly_Explode1",
            "field": "pos",
            "predicted": [7, 3],
            "actual": [6, 3],
        },
        {
            "uid": 364,
            "type": "Jelly_Explode1",
            "field": "status.fire",
            "predicted": True,
            "actual": False,
        },
    ])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        diff, "Prime_Leap", "attack"
    ) is False


def test_prime_leap_settle_retry_rejects_mixed_or_worse_live_diff():
    mixed = DiffResult(
        tile_diffs=[{
            "x": 5,
            "y": 2,
            "field": "building_hp",
            "predicted": 1,
            "actual": 2,
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 5,
            "actual": 4,
        }],
    )
    worse_live = DiffResult(tile_diffs=[{
        "x": 5,
        "y": 2,
        "field": "building_hp",
        "predicted": 2,
        "actual": 1,
    }])

    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        mixed, "Prime_Leap_AB", "attack"
    ) is False
    assert cmd_mod._is_transient_delayed_multihit_damage_diff(
        worse_live, "Prime_Leap", "attack"
    ) is False


def test_prime_leap_settle_uses_newer_nontransient_reread():
    initial = DiffResult(tile_diffs=[{
        "x": 4,
        "y": 2,
        "field": "building_hp",
        "predicted": 1,
        "actual": 2,
    }])
    reread = DiffResult(tile_diffs=[
        {
            "x": 4,
            "y": 2,
            "field": "building_hp",
            "predicted": 1,
            "actual": 2,
        },
        {
            "x": 5,
            "y": 2,
            "field": "building_hp",
            "predicted": 2,
            "actual": 1,
        },
    ])

    assert cmd_mod._delayed_multihit_reread_became_nontransient(
        initial,
        reread,
        "Prime_Leap",
        "attack",
    ) is True


def test_repair_platform_move_diff_gets_settle_retry():
    diff = DiffResult(
        unit_diffs=[{
            "uid": 2,
            "type": "PitcherMech",
            "field": "hp",
            "predicted": 3,
            "actual": 1,
        }],
        tile_diffs=[{
            "x": 6,
            "y": 3,
            "field": "repair_platform",
            "predicted": False,
            "actual": True,
        }],
        scalar_diffs=[{
            "field": "repair_platforms_used",
            "predicted": 2,
            "actual": 1,
        }],
    )

    assert cmd_mod._is_transient_delayed_repair_platform_diff(
        diff, "move"
    ) is True


def test_repair_platform_settle_retry_rejects_mixed_grid_loss():
    diff = DiffResult(
        unit_diffs=[{
            "uid": 2,
            "type": "PitcherMech",
            "field": "hp",
            "predicted": 3,
            "actual": 1,
        }],
        tile_diffs=[{
            "x": 6,
            "y": 3,
            "field": "repair_platform",
            "predicted": False,
            "actual": True,
        }],
        scalar_diffs=[
            {
                "field": "repair_platforms_used",
                "predicted": 2,
                "actual": 1,
            },
            {
                "field": "grid_power",
                "predicted": 6,
                "actual": 5,
            },
        ],
    )

    assert cmd_mod._is_transient_delayed_repair_platform_diff(
        diff, "move"
    ) is False


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
