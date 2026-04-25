"""Passive_Medical ("Medical Supplies"): all pilots survive mech death.

The passive zeroes the permanent-pilot-loss component of the mech-death
penalty. The base mech_killed penalty (grid/HP consequences of the mech
actually being destroyed) is unaffected — only `mech_killed * pilot_value`
is gated.

Covers:
- Bridge-dict detection: any player mech carrying `Passive_Medical` in
  its weapons list flips `board.medical_supplies = True` (squad-wide).
- Evaluator gating: a dead mech with pilot_value > 0 costs less when
  medical_supplies is True vs False, by exactly `mech_killed * pilot_value`.
"""

from __future__ import annotations

from src.model.board import Board, Unit
from src.solver.evaluate import evaluate, EvalWeights


def _bridge_data_with_mech(weapons: list[str]) -> dict:
    """Minimal bridge payload: 1 player mech at (3, 3) with given weapons."""
    return {
        "phase": "combat_player",
        "grid_power": 5,
        "grid_power_max": 7,
        "current_turn": 2,
        "total_turns": 5,
        "units": [
            {
                "uid": 100,
                "type": "JudoMech",
                "x": 3,
                "y": 3,
                "hp": 3,
                "max_hp": 3,
                "team": 1,
                "mech": True,
                "move_speed": 4,
                "weapons": weapons,
            }
        ],
        "tiles": [],
    }


def test_bridge_detects_passive_medical():
    """A mech carrying Passive_Medical flips board.medical_supplies."""
    data = _bridge_data_with_mech(["Prime_Punchmech", "Passive_Medical"])
    board = Board.from_bridge_data(data)
    assert board.medical_supplies is True


def test_bridge_no_passive_medical_when_absent():
    """Without Passive_Medical, the flag stays False."""
    data = _bridge_data_with_mech(["Prime_Punchmech", "Passive_ForceAmp"])
    board = Board.from_bridge_data(data)
    assert board.medical_supplies is False
    # Sanity: ForceAmp still detected (confirms same code path).
    assert board.force_amp is True


def _board_with_mech_on_lethal_env(pilot_value: float, medical: bool) -> Board:
    """Mech standing on a lethal env-danger tile. The evaluator's env-lethal
    branch applies mech_killed + pilot penalty (this is where the pilot-loss
    gating is observable in the Python path — the Python `mechs()` helper
    filters out hp<=0 units, so the main mech-loop's dead branch is
    unreachable in pure-Python scoring; env-lethal is the exercisable site).
    """
    b = Board()
    b.grid_power = 5
    b.grid_power_max = 7
    b.medical_supplies = medical
    # Lethal env at (3, 3): damage=5, kill=True.
    b.environment_danger.add((3, 3))
    b.environment_danger_v2[(3, 3)] = (5, True)
    b.units = [
        Unit(
            uid=1,
            type="JudoMech",
            x=3,
            y=3,
            hp=3,          # alive — env-danger loop iterates via mechs()
            max_hp=3,
            team=1,
            is_mech=True,
            move_speed=4,
            flying=False,
            massive=True,
            armor=False,
            pushable=True,
            weapon="",
            pilot_value=pilot_value,
        )
    ]
    return b


def test_medical_supplies_zeroes_pilot_penalty():
    """Mech on a lethal env tile with pilot_value=3:
    with Medical Supplies the pilot-loss component (|mech_killed|*3) is waived.
    """
    w = EvalWeights()
    without = evaluate(_board_with_mech_on_lethal_env(3.0, medical=False),
                       spawn_points=[], weights=w,
                       current_turn=2, total_turns=5)
    with_med = evaluate(_board_with_mech_on_lethal_env(3.0, medical=True),
                        spawn_points=[], weights=w,
                        current_turn=2, total_turns=5)

    # Medical Supplies must strictly improve the score of a board where a
    # veteran pilot is about to be permanently lost.
    assert with_med > without

    # Gap must equal exactly the saved pilot penalty: |mech_killed| * pilot_value.
    expected_gap = abs(w.mech_killed) * 3.0
    actual_gap = with_med - without
    assert abs(actual_gap - expected_gap) < 1e-6, (
        f"expected gap {expected_gap}, got {actual_gap} "
        f"(without={without}, with_med={with_med})"
    )


def test_medical_supplies_does_not_change_score_when_no_pilot_value():
    """pilot_value=0 → Medical flag has no effect (no pilot-value term to zero)."""
    w = EvalWeights()
    without = evaluate(_board_with_mech_on_lethal_env(0.0, medical=False),
                       spawn_points=[], weights=w,
                       current_turn=2, total_turns=5)
    with_med = evaluate(_board_with_mech_on_lethal_env(0.0, medical=True),
                        spawn_points=[], weights=w,
                        current_turn=2, total_turns=5)
    assert abs(with_med - without) < 1e-6
