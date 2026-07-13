"""Simulator v351 webbed-enemy attack semantics regressions."""

from __future__ import annotations

import json

import pytest

from src.loop import commands as cmd_mod
from src.loop.commands import (
    _attacker_smoked_at_attack_start,
    _bv,
    _classify_resist_outcome,
    _compute_resist_observations,
)
from src.loop.session import RunSession
from src.model.board import Board, Unit
from src.solver.evaluate import EvalWeights, evaluate

try:
    import itb_solver  # type: ignore
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _unit(
    *,
    uid: int,
    team: int,
    x: int,
    y: int,
    hp: int,
    is_mech: bool,
    web: bool = False,
) -> Unit:
    return Unit(
        uid=uid,
        type="PunchMech" if is_mech else "Firefly1",
        x=x,
        y=y,
        hp=hp,
        max_hp=3,
        team=team,
        is_mech=is_mech,
        move_speed=3,
        flying=False,
        massive=is_mech,
        armor=False,
        pushable=True,
        weapon="Prime_Punchmech" if is_mech else "FireflyAtk1",
        web=web,
    )


def test_python_low_hp_risk_counts_webbed_enemy():
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    board.units = [
        _unit(uid=1, team=1, x=2, y=3, hp=1, is_mech=True),
        _unit(uid=10, team=6, x=2, y=2, hp=3, is_mech=False, web=True),
    ]
    baseline = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=0.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    risky = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=-200.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )

    assert abs(risky - baseline + 200.0) < 1.0


def test_python_low_hp_risk_handles_passive_psion_and_snowmine_exceptions():
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    board.units = [
        _unit(uid=1, team=1, x=2, y=3, hp=1, is_mech=True),
        _unit(uid=10, team=6, x=2, y=2, hp=3, is_mech=False),
    ]
    board.units[1].type = "Jelly_Armor1"
    baseline = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=0.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    passive = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=-200.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    assert abs(passive - baseline) < 1.0

    board.units[1].type = "Snowmine1"
    board.tiles[2][2].smoke = True
    snowmine_baseline = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=0.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    smoke_immune = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=-200.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    assert abs(smoke_immune - snowmine_baseline + 200.0) < 1.0

    board.units[1].web = True
    webbed = evaluate(
        board,
        weights=EvalWeights(mech_low_hp_risk=-200.0),
        current_turn=1,
        total_turns=5,
        remaining_spawns=1,
    )
    assert abs(webbed - snowmine_baseline) < 1.0


def test_resist_probe_does_not_treat_web_as_disruption():
    outcome = _classify_resist_outcome(
        1,
        1,
        attacker_found=True,
        attacker_pos_changed=False,
        attacker_webbed=True,
        attacker_smoked=False,
        target_smoked=False,
    )

    assert outcome == "resisted"


def test_resist_probe_does_not_treat_target_smoke_as_disruption():
    outcome = _classify_resist_outcome(
        1,
        1,
        attacker_found=True,
        attacker_pos_changed=False,
        attacker_webbed=False,
        attacker_smoked=False,
        target_smoked=True,
    )

    assert outcome == "resisted"


def test_resist_probe_treats_attacker_smoke_as_disruption():
    outcome = _classify_resist_outcome(
        1,
        1,
        attacker_found=True,
        attacker_pos_changed=False,
        attacker_webbed=False,
        attacker_smoked=True,
        target_smoked=False,
    )

    assert outcome == "attacker_smoked"


def test_resist_probe_fails_closed_without_attack_start_smoke_provenance():
    outcome = _classify_resist_outcome(
        1,
        1,
        attacker_found=True,
        attacker_pos_changed=False,
        attacker_webbed=False,
        attacker_smoked=None,
        target_smoked=False,
    )

    assert outcome == "unknown"


def test_attack_start_smoke_includes_pending_terratide_smoke():
    board = _resist_observation_board(attacker_smoked_after=False)
    board.environment_smoke.add((2, 2))

    assert _attacker_smoked_at_attack_start(board, board.units[0]) is True


def test_resist_probe_write_failure_preserves_blocking_threat_audit(monkeypatch):
    session = RunSession(run_id="v351")
    threat_audit = {
        "status": "WARN",
        "still_threatened_count": 1,
        "entries": [{"target_visual": "A1"}],
    }

    def fail_probe(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cmd_mod, "_log_resist_probe", fail_probe)
    error = cmd_mod._log_post_action_resist_probe(
        session,
        Board(),
        {"phase": "combat_player"},
        threat_audit,
    )

    assert error == {"type": "OSError", "message": "disk full"}
    assert threat_audit["still_threatened_count"] == 1
    assert threat_audit["resist_probe_error"] == error
    assert cmd_mod._threat_audit_requires_block(
        threat_audit,
        {"status": "CLEAN", "blocking": False},
        session,
    ) is True


def test_threat_audit_error_fails_closed():
    assert cmd_mod._threat_audit_requires_block(
        {"status": "ERROR", "error": "audit unavailable"},
        {"status": "CLEAN", "blocking": False},
        RunSession(run_id="v351"),
    ) is True


@pytest.mark.parametrize(
    ("board", "bridge_data", "expected_error"),
    [
        (None, {}, "post_action_audit_board_missing"),
        (Board(), None, "post_action_audit_bridge_data_missing"),
    ],
)
def test_missing_post_action_audit_evidence_fails_closed(
    board,
    bridge_data,
    expected_error,
):
    error = cmd_mod._post_action_audit_evidence_error(
        board,
        bridge_data,
        expected_turn=3,
    )

    assert error == {"status": "ERROR", "error": expected_error}
    assert cmd_mod._threat_audit_requires_block(
        error,
        {"status": "CLEAN", "blocking": False},
        RunSession(run_id="v351"),
    ) is True


@pytest.mark.parametrize(
    ("bridge_data", "expected_error"),
    [
        (
            {"phase": "combat_enemy", "turn": 3},
            "post_action_audit_phase_mismatch",
        ),
        (
            {"phase": "combat_player", "turn": 2},
            "post_action_audit_turn_mismatch",
        ),
        (
            {
                "phase": "combat_player",
                "turn": 3,
                "in_active_mission": False,
            },
            "post_action_audit_mission_inactive",
        ),
    ],
)
def test_stale_post_action_audit_evidence_fails_closed(
    bridge_data,
    expected_error,
):
    error = cmd_mod._post_action_audit_evidence_error(
        Board(),
        bridge_data,
        expected_turn=3,
    )

    assert error["status"] == "ERROR"
    assert error["error"] == expected_error
    assert cmd_mod._threat_audit_requires_block(
        error,
        {"status": "CLEAN", "blocking": False},
        RunSession(run_id="v351"),
    ) is True


def test_fresh_post_action_audit_evidence_is_accepted():
    assert cmd_mod._post_action_audit_evidence_error(
        Board(),
        {
            "phase": "combat_player",
            "turn": 3,
            "in_active_mission": True,
        },
        expected_turn=3,
    ) is None


def _resist_observation_board(*, attacker_smoked_after: bool) -> Board:
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    board.units = [
        _unit(uid=10, team=6, x=2, y=2, hp=3, is_mech=False),
    ]
    board.tiles[2][2].smoke = attacker_smoked_after
    board.tiles[3][3].terrain = "building"
    board.tiles[3][3].building_hp = 1
    return board


def _previous_resist_entry(*, attacker_smoked_at_attack_start: bool) -> dict:
    return {
        "grid_power": 7,
        "telegraphed_building_attacks": [{
            "attacker_uid": 10,
            "attacker_type": "Firefly1",
            "attacker_pos": _bv(2, 2),
            "attacker_webbed_at_probe": False,
            "attacker_smoked_at_attack_start": (
                attacker_smoked_at_attack_start
            ),
            "target_pos": _bv(3, 3),
            "target_building_hp_before": 1,
        }],
    }


def test_resist_observation_uses_latched_smoke_not_clear_post_state():
    observations = _compute_resist_observations(
        _previous_resist_entry(attacker_smoked_at_attack_start=True),
        _resist_observation_board(attacker_smoked_after=False),
        7,
    )

    assert observations[0]["attacker_smoked"] is True
    assert observations[0]["attacker_smoked_after"] is False
    assert observations[0]["inferred_outcome"] == "attacker_smoked"


def test_resist_observation_ignores_smoke_created_after_attack_start():
    observations = _compute_resist_observations(
        _previous_resist_entry(attacker_smoked_at_attack_start=False),
        _resist_observation_board(attacker_smoked_after=True),
        7,
    )

    assert observations[0]["attacker_smoked"] is False
    assert observations[0]["attacker_smoked_after"] is True
    assert observations[0]["inferred_outcome"] == "resisted"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_projected_webbed_enemy_receives_queued_attack():
    bridge = {
        "grid_power": 7,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "remaining_spawns": 0,
        "spawning_tiles": [],
        "tiles": [
            {"x": 0, "y": 7, "terrain": "building", "building_hp": 1},
        ],
        "units": [
            {
                "uid": 10,
                "type": "Firefly1",
                "x": 0,
                "y": 0,
                "hp": 3,
                "max_hp": 3,
                "team": 6,
                "mech": False,
                "move": 3,
                "base_move": 3,
                "active": False,
                "web": True,
                "weapons": ["FireflyAtk1"],
                "queued_target": [-1, -1],
            },
        ],
    }

    projected = json.loads(
        itb_solver.project_plan(json.dumps(bridge), "[]")
    )
    board = json.loads(projected["board_json"])
    enemy = next(unit for unit in board["units"] if unit["uid"] == 10)

    assert enemy["web"] is True
    assert enemy["queued_target"] == [0, 7]
    assert enemy["has_queued_attack"] is True
