"""Renfield Bomb (BigBomb) — Mission_Final_Cave lifecycle NPC.

Per `scripts/missions/final/mission_final_two.lua:179-188`:
    BigBomb = { Health=4, Neutral=true, Corpse=false, IgnoreFire=true,
                MoveSpeed=0, DefaultTeam=TEAM_PLAYER, IsPortrait=false }

The bomb sits on the board and self-detonates on a fixed turn limit,
clearing all enemies. If it is destroyed, mission source drops a replacement
and adds 2 to TurnLimit. Simulator v406 applies that exact extension, records
the replacement as pending, and retains source-reachable candidates for its
stable projected snapshot. It deliberately does not fabricate the native
callback timing or random coordinate. The exact Windows outcome map proves
that bomb loss delays the countdown rather than directly losing the mission.
The model wires this in three places:

1. `data/known_types.json` lists "BigBomb" so the research-gate doesn't
   block the final mission.
2. `src/model/pawn_stats.py` has stats so move/push semantics resolve
   (move_speed=0, pushable=True, ignore_fire=True). Pushability follows the
   inherited source default and live final-cave evidence.
3. `Board.bigbomb_alive` flips false when the current pawn dies, while
   `bigbomb_replacement_pending` preserves the guaranteed lifecycle edge.
   The evaluator still strongly disfavors destroying the current bomb and the
   safety gate remains non-overridable until a live board resolves its native
   replacement coordinate.

Covers:
- Bridge detection: a BigBomb at hp>0 sets board.bigbomb_alive=True.
- Projected pending state round-trips only for Mission_Final_Cave with no live
  BigBomb and a nonempty candidate list.
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

import pytest

from src.model.board import Board, Unit, BoardTile
from src.model.pawn_stats import get_pawn_stats, ALL_PAWN_STATS
from src.solver.evaluate import evaluate, EvalWeights

try:
    import itb_solver
except ImportError:  # pragma: no cover - source-only environments
    itb_solver = None


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
        pushable=True,
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
    assert stats.pushable is True          # inherited default + live push evidence
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


def test_projected_replacement_boundary_roundtrips_without_fake_bomb():
    data = {
        "phase": "combat_player",
        "mission_id": "Mission_Final_Cave",
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 3,
        "total_turns": 6,
        "bigbomb_replacement_pending": True,
        "bigbomb_replacement_snapshot_candidates": [[2, 2], [3, 3]],
        "units": [],
        "tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.bigbomb_alive is False
    assert board.bigbomb_replacement_pending is True
    assert board.bigbomb_replacement_snapshot_candidates == [(2, 2), (3, 3)]

    copied = board.copy()
    assert copied.bigbomb_replacement_pending is True
    assert copied.bigbomb_replacement_snapshot_candidates == [(2, 2), (3, 3)]


def test_projected_replacement_boundary_fails_closed_outside_exact_shape():
    base = {
        "mission_id": "Mission_Final_Cave",
        "turn": 3,
        "total_turns": 6,
        "bigbomb_replacement_pending": True,
        "bigbomb_replacement_snapshot_candidates": [[2, 2]],
        "units": [],
        "tiles": [],
    }
    wrong_mission = dict(base, mission_id="Mission_Battle")
    assert Board.from_bridge_data(wrong_mission).bigbomb_replacement_pending is False

    empty_candidates = dict(base, bigbomb_replacement_snapshot_candidates=[])
    assert Board.from_bridge_data(empty_candidates).bigbomb_replacement_pending is False

    with_live_bomb = dict(base)
    with_live_bomb["units"] = [{
        "uid": 200,
        "type": "BigBomb",
        "x": 3,
        "y": 3,
        "hp": 4,
        "max_hp": 4,
        "team": 1,
        "mech": False,
        "move_speed": 0,
    }]
    parsed = Board.from_bridge_data(with_live_bomb)
    assert parsed.bigbomb_alive is True
    assert parsed.bigbomb_replacement_pending is False


@pytest.mark.skipif(itb_solver is None, reason="itb_solver wheel not installed")
def test_rust_projection_emits_exact_replacement_boundary_without_fake_bomb():
    board = {
        "mission_id": "Mission_Final_Cave",
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 2,
        "total_turns": 4,
        "spawning_tiles": [],
        "attack_order": [300],
        "tiles": [{
            "x": 5,
            "y": 5,
            "terrain": "building",
            "building_hp": 1,
        }],
        "units": [
            {
                "uid": 200,
                "type": "BigBomb",
                "x": 3,
                "y": 3,
                "hp": 4,
                "max_hp": 4,
                "team": 1,
                "mech": False,
                "move": 0,
                "pushable": True,
                "weapons": [],
            },
            {
                "uid": 0,
                "type": "PunchMech",
                "x": 2,
                "y": 2,
                "hp": 3,
                "max_hp": 3,
                "team": 1,
                "mech": True,
                "move": 3,
                "pushable": True,
                "weapons": ["Prime_Punchmech"],
            },
            {
                "uid": 300,
                "type": "FireflyBoss",
                "x": 3,
                "y": 2,
                "hp": 6,
                "max_hp": 6,
                "team": 6,
                "mech": False,
                "move": 2,
                "pushable": True,
                "weapons": ["FireflyBossAtk1"],
                "has_queued_attack": True,
                "queued_origin": [3, 2],
                "queued_target": [3, 3],
            },
        ],
    }

    raw = itb_solver.project_plan(json.dumps(board), "[]")
    projected = json.loads(json.loads(raw)["board_json"])

    assert projected["turn"] == 3
    assert projected["total_turns"] == 6
    assert projected["bigbomb_replacement_pending"] is True
    assert len(projected["bigbomb_replacement_snapshot_candidates"]) == 14
    assert [2, 2] not in projected["bigbomb_replacement_snapshot_candidates"]
    assert [5, 5] not in projected["bigbomb_replacement_snapshot_candidates"]
    assert all(unit["type"] != "BigBomb" for unit in projected["units"])


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
    """The current-bomb penalty remains unscaled despite guaranteed recovery.

    v406 models the +2 extension at full-turn projection, while this evaluator
    unit test still covers the immediate alive-to-dead action edge.
    """
    w = EvalWeights()
    assert w.bigbomb_killed == -200000
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
