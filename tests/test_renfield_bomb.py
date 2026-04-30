"""Renfield Bomb (BigBomb) — Mission_Final_Cave win-condition NPC.

Per `scripts/missions/final/mission_final_two.lua:179-188`:
    BigBomb = { Health=4, Neutral=true, Corpse=false, IgnoreFire=true,
                MoveSpeed=0, DefaultTeam=TEAM_PLAYER, IsPortrait=false }

The bomb sits on the board and self-detonates on a fixed turn limit,
clearing all enemies. Defending it is the win condition; losing it fails
the run. The simulator wires this in three places:

1. `data/known_types.json` lists "BigBomb" so the research-gate doesn't
   block the final mission.
2. `src/model/pawn_stats.py` has stats so move/push semantics resolve
   (move_speed=0, pushable=False, ignore_fire=True).
3. `Board.bigbomb_alive` (Python and Rust) flips false the moment the
   last BigBomb pawn drops to hp <= 0 — and the evaluator scores the
   alive→dead transition with `bigbomb_killed` (default -200000), a
   mission-failure penalty layered on top of the standard
   `friendly_npc_killed` (-20000) NPC penalty.

Covers:
- Bridge detection: a BigBomb at hp>0 sets board.bigbomb_alive=True.
- Pawn-stats lookup: BigBomb is registered with the documented stats.
- Evaluator transition: bomb alive→dead pays bigbomb_killed once, NOT
  scaled by future_factor.
- Evaluator stable: a board where the bomb stays alive is unaffected by
  the bigbomb_killed weight.
- known_types.json: BigBomb is in the observed_pawn_types list.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.model.board import Board, Unit, BoardTile
from src.model.pawn_stats import get_pawn_stats, ALL_PAWN_STATS
from src.solver.evaluate import evaluate, EvalWeights


def _make_minimal_bomb_board(bomb_hp: int) -> Board:
    """Construct a board with a single BigBomb at (3, 3). Used by both
    the alive and post-death cases — the only thing that varies is hp.
    """
    b = Board()
    b.grid_power = 5
    b.grid_power_max = 7
    bomb = Unit(
        uid=200,
        type="BigBomb",
        x=3, y=3,
        hp=bomb_hp,
        max_hp=4,
        team=1,                 # TEAM_PLAYER (Lua DefaultTeam = TEAM_PLAYER)
        is_mech=False,          # Bridge sets IsMech() = False for non-mech NPCs
        move_speed=0,
        flying=False,
        massive=False,
        armor=False,
        pushable=False,
        weapon="",
    )
    b.units = [bomb]
    b.bigbomb_alive = bomb_hp > 0
    return b


# ── pawn_stats ──────────────────────────────────────────────────────────────


def test_pawn_stats_registers_bigbomb():
    """`BigBomb` must be in ALL_PAWN_STATS so move/push semantics resolve."""
    assert "BigBomb" in ALL_PAWN_STATS
    stats = get_pawn_stats("BigBomb")
    assert stats.move_speed == 0           # Lua MoveSpeed = 0
    assert stats.pushable is False         # bomb sits in place
    assert stats.ignore_fire is True       # Lua IgnoreFire = true
    # Default class_type / leader / ranged should remain at defaults —
    # the bomb is purely passive and these knobs aren't relevant.


# ── known_types.json ────────────────────────────────────────────────────────


def test_known_types_includes_bigbomb_and_final_pawns():
    """`data/known_types.json` must list BigBomb (and the other final-mission
    pawn types) so the research-gate doesn't trigger a `RESEARCH_REQUIRED`
    every time the player enters the volcano caverns."""
    repo_root = Path(__file__).parent.parent
    with open(repo_root / "data" / "known_types.json") as f:
        kt = json.load(f)
    obs = set(kt["observed_pawn_types"])
    # BigBomb is the new objective NPC.
    assert "BigBomb" in obs
    # Final-mission entourage that previously triggered research gates.
    for name in ("Crab1", "Blob1", "Blobber1", "Jelly_Lava1"):
        assert name in obs, f"{name} missing from observed_pawn_types"


# ── bridge detection ────────────────────────────────────────────────────────


def test_bridge_data_sets_bigbomb_alive_when_alive():
    """A BigBomb at hp>0 in bridge payload flips board.bigbomb_alive=True."""
    data = {
        "phase": "combat_player",
        "grid_power": 5,
        "grid_power_max": 7,
        "current_turn": 2,
        "total_turns": 5,
        "units": [
            {
                "uid": 200,
                "type": "BigBomb",
                "x": 3, "y": 3,
                "hp": 4, "max_hp": 4,
                "team": 1,
                "mech": False,
                "move_speed": 0,
            }
        ],
        "tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.bigbomb_alive is True


def test_bridge_data_leaves_bigbomb_alive_false_when_dead():
    """A BigBomb at hp=0 leaves bigbomb_alive=False (the only payload entry
    represents the corpse-suppressed dead bomb on a verify_action read)."""
    data = {
        "phase": "combat_player",
        "grid_power": 5,
        "grid_power_max": 7,
        "current_turn": 2,
        "total_turns": 5,
        "units": [
            {
                "uid": 200,
                "type": "BigBomb",
                "x": 3, "y": 3,
                "hp": 0, "max_hp": 4,
                "team": 1,
                "mech": False,
                "move_speed": 0,
            }
        ],
        "tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.bigbomb_alive is False


def test_bridge_data_no_bomb_leaves_flag_false():
    """Missions without a bomb (every non-final mission) keep the flag False."""
    data = {
        "phase": "combat_player",
        "grid_power": 5,
        "grid_power_max": 7,
        "current_turn": 2,
        "total_turns": 5,
        "units": [],
        "tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.bigbomb_alive is False


# ── evaluator transition ────────────────────────────────────────────────────


def test_evaluator_pays_bigbomb_killed_on_alive_to_dead_transition():
    """Evaluating a board where the bomb just died (with bigbomb_was_alive=True
    flagged from the pre-action snapshot) must subtract w.bigbomb_killed."""
    w = EvalWeights()
    dead_board = _make_minimal_bomb_board(bomb_hp=0)
    score_with_transition = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=True,
        current_turn=2, total_turns=5,
    )
    score_without_transition = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=False,
        current_turn=2, total_turns=5,
    )
    # The transition must subtract exactly w.bigbomb_killed.
    expected_gap = w.bigbomb_killed   # negative number
    actual_gap = score_with_transition - score_without_transition
    assert abs(actual_gap - expected_gap) < 1e-6, (
        f"expected gap {expected_gap}, got {actual_gap}"
    )


def test_evaluator_does_not_pay_bigbomb_killed_when_bomb_survives():
    """A bomb that's still alive after mech actions costs nothing — the
    transition only fires on alive→dead."""
    w = EvalWeights()
    alive_board = _make_minimal_bomb_board(bomb_hp=4)
    with_flag = evaluate(
        alive_board, spawn_points=[], weights=w,
        bigbomb_was_alive=True,
        current_turn=2, total_turns=5,
    )
    without_flag = evaluate(
        alive_board, spawn_points=[], weights=w,
        bigbomb_was_alive=False,
        current_turn=2, total_turns=5,
    )
    assert abs(with_flag - without_flag) < 1e-6


def test_bigbomb_killed_is_not_scaled_by_future_factor():
    """The penalty MUST NOT scale by future_factor — losing the bomb on the
    final turn is just as catastrophic as losing it on the first turn.
    Both calls below should subtract the full -200000 (default)."""
    w = EvalWeights()
    dead_board = _make_minimal_bomb_board(bomb_hp=0)

    # First combat turn (ff ≈ 1.0)
    early = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=True,
        current_turn=1, total_turns=5,
    )
    early_no_transition = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=False,
        current_turn=1, total_turns=5,
    )

    # Final combat turn (ff ≈ 0.0)
    late = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=True,
        current_turn=5, total_turns=5,
    )
    late_no_transition = evaluate(
        dead_board, spawn_points=[], weights=w,
        bigbomb_was_alive=False,
        current_turn=5, total_turns=5,
    )

    early_gap = early - early_no_transition
    late_gap = late - late_no_transition
    # Both gaps must equal w.bigbomb_killed exactly.
    assert abs(early_gap - w.bigbomb_killed) < 1e-6
    assert abs(late_gap - w.bigbomb_killed) < 1e-6
    # And they must be equal to each other (no future_factor scaling).
    assert abs(early_gap - late_gap) < 1e-6
