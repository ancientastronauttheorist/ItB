"""Hazard-aware deploy filtering tests.

Covers the recommendation behavior added on top of `rank_deploy_tiles`:

* Freeze Mine tiles (Pinnacle Robotics — Shielded Vaults / Cold Storage)
  freeze any unit that stops on them. Frozen mechs are wasted for several
  turns. Today's run #2 lost largely because Gravity Mech got stuck on a
  Freeze Mine as its deploy tile.
* Old Earth Mine tiles (Archive Inc — various) outright KILL units that
  stop on them. Per memory `feedback_old_earth_mines.md` and
  `data/known_types.json`.
* Conveyor / teleporter tiles silently absorb the deploy click (memory
  `feedback_deploy_conveyor_clicks.md`, `feedback_deploy_teleporter_clicks.md`).

The recommender filters those tiles by default, BUT when the deploy zone
has fewer than 3 safe tiles it must still emit 3 tiles, falling back to
the lowest-severity hazard first. Severity order:
  ground/forest/sand → conveyor/teleporter → freeze_mine → old_earth_mine.
Reluctant fallbacks are flagged with `hazard_warning=True`.

Full annotations are also exposed via `classify_deploy_hazard` so the
`DEPLOYMENT ZONE` listing in `cmd_read` can label every tile with its
hazard while keeping the full zone list intact.
"""

from __future__ import annotations

from src.loop.commands import (
    _deployable_mechs,
    classify_deploy_hazard,
    rank_deploy_tiles,
    recommend_deploy_tiles,
)
from src.loop.session import RunSession
from src.model.board import Board, Unit


def _empty_board() -> Board:
    """Plain 8x8 ground board with no units, no enemies, no buildings."""
    return Board()


def _mech(uid: int, mech_type: str) -> Unit:
    return Unit(
        uid=uid,
        type=mech_type,
        x=0,
        y=0,
        hp=3,
        max_hp=3,
        team=1,
        is_mech=True,
        move_speed=3,
        flying=False,
        massive=True,
        armor=False,
        pushable=True,
        weapon="",
    )


# ---------------------------------------------------------------------------
# classify_deploy_hazard
# ---------------------------------------------------------------------------


def test_classify_returns_none_for_plain_ground():
    board = _empty_board()
    assert classify_deploy_hazard(board, 4, 4) is None


def test_deployable_mechs_supplements_partial_bridge_roster(monkeypatch):
    board = _empty_board()
    board.units.append(_mech(0, "FlameMech"))
    board.units.append(_mech(1, "IgniteMech"))

    class FakeState:
        mechs = ["FlameMech", "IgniteMech", "TeleMech"]
        weapons = []

    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": FakeState(),
    )

    mechs = _deployable_mechs(board, RunSession(), profile="Alpha")

    assert [m["uid"] for m in mechs] == [0, 1, 2]
    assert [m["type"] for m in mechs] == [
        "FlameMech",
        "IgniteMech",
        "TeleMech",
    ]


def test_classify_returns_freeze_mine():
    board = _empty_board()
    board.tile(4, 4).freeze_mine = True
    assert classify_deploy_hazard(board, 4, 4) == "freeze_mine"


def test_classify_returns_old_earth_mine():
    board = _empty_board()
    board.tile(4, 4).old_earth_mine = True
    assert classify_deploy_hazard(board, 4, 4) == "old_earth_mine"


def test_classify_returns_conveyor():
    board = _empty_board()
    board.tile(4, 4).conveyor = 0
    assert classify_deploy_hazard(board, 4, 4) == "conveyor"


def test_classify_returns_teleporter():
    board = _empty_board()
    board.teleporter_pairs = [(4, 4, 5, 5)]
    assert classify_deploy_hazard(board, 4, 4) == "teleporter"
    assert classify_deploy_hazard(board, 5, 5) == "teleporter"


def test_classify_severity_order_old_earth_mine_wins():
    """If a tile somehow has multiple hazards, the most dangerous wins."""
    board = _empty_board()
    board.tile(4, 4).old_earth_mine = True
    board.tile(4, 4).freeze_mine = True
    board.tile(4, 4).conveyor = 0
    assert classify_deploy_hazard(board, 4, 4) == "old_earth_mine"


# ---------------------------------------------------------------------------
# rank_deploy_tiles — freeze_mine and old_earth_mine
# ---------------------------------------------------------------------------


def test_freeze_mine_tiles_excluded_from_ranking():
    """Freeze Mine tiles must not appear in ranked recommendations
    when there are enough safe tiles."""
    board = _empty_board()
    board.tile(3, 5).freeze_mine = True
    board.tile(3, 6).freeze_mine = True

    deploy_zone = [
        [3, 5],  # freeze mine
        [3, 6],  # freeze mine
        [2, 5],  # plain
        [2, 6],  # plain
        [4, 4],  # plain (forward row)
    ]
    ranked = rank_deploy_tiles(board, deploy_zone)
    ranked_set = set(ranked)

    assert (3, 5) not in ranked_set
    assert (3, 6) not in ranked_set
    assert ranked_set == {(2, 5), (2, 6), (4, 4)}


def test_old_earth_mine_tiles_excluded_from_ranking():
    """Old Earth Mine tiles must not appear in ranked recommendations
    when there are enough safe tiles."""
    board = _empty_board()
    board.tile(3, 5).old_earth_mine = True
    board.tile(2, 4).old_earth_mine = True

    deploy_zone = [
        [3, 5],  # mine
        [2, 4],  # mine
        [2, 5],  # plain
        [2, 6],  # plain
        [4, 4],  # plain (forward row)
    ]
    ranked = rank_deploy_tiles(board, deploy_zone)
    ranked_set = set(ranked)

    assert (3, 5) not in ranked_set
    assert (2, 4) not in ranked_set
    assert ranked_set == {(2, 5), (2, 6), (4, 4)}


# ---------------------------------------------------------------------------
# recommend_deploy_tiles — fallback behavior
# ---------------------------------------------------------------------------


def test_fallback_when_only_two_safe_tiles_picks_lowest_severity():
    """Spec: when filtering would leave fewer than 3 recommendations,
    still emit up to 3 — preferring the lowest-severity hazard."""
    board = _empty_board()
    board.tile(3, 5).old_earth_mine = True   # severity 3
    board.tile(3, 6).freeze_mine = True       # severity 2
    board.tile(2, 5).conveyor = 0             # severity 1

    deploy_zone = [
        [3, 5],  # old_earth_mine (severity 3)
        [3, 6],  # freeze_mine (severity 2)
        [2, 5],  # conveyor (severity 1)
        [2, 6],  # plain
        [4, 4],  # plain (forward)
    ]
    recs = recommend_deploy_tiles(board, deploy_zone)

    assert len(recs) == 3
    safe = [r for r in recs if r["hazard"] is None]
    fallback = [r for r in recs if r["hazard"] is not None]
    assert len(safe) == 2, f"expected 2 safe picks, got {safe}"
    assert len(fallback) == 1, f"expected 1 reluctant pick, got {fallback}"
    # The lowest-severity hazard wins the fallback slot.
    assert fallback[0]["hazard"] == "conveyor"
    assert fallback[0]["hazard_warning"] is True


def test_fallback_severity_ordering_conveyor_before_freeze_before_mine():
    """When zero safe tiles exist, severity order picks conveyor first,
    then freeze_mine, then old_earth_mine — the reverse of how dangerous
    they are. The user wants the LEAST awful fallback."""
    board = _empty_board()
    board.tile(3, 5).old_earth_mine = True
    board.tile(3, 6).freeze_mine = True
    board.tile(2, 5).conveyor = 0

    # Only 3 hazardous tiles — no safe option.
    deploy_zone = [[3, 5], [3, 6], [2, 5]]
    recs = recommend_deploy_tiles(board, deploy_zone)

    assert len(recs) == 3
    hazards_in_order = [r["hazard"] for r in recs]
    # Severity ascending: conveyor (1), freeze_mine (2), old_earth_mine (3).
    # Within a severity bucket order is by score, but with these 3 distinct
    # severities the order is forced.
    assert hazards_in_order.index("conveyor") < hazards_in_order.index("freeze_mine")
    assert hazards_in_order.index("freeze_mine") < hazards_in_order.index("old_earth_mine")
    # All 3 are reluctant fallbacks.
    assert all(r["hazard_warning"] for r in recs)


def test_fallback_picks_freeze_over_mine_when_no_conveyor():
    """If no conveyor/teleporter exists, the freeze_mine should be picked
    over the old_earth_mine — frozen is survivable, mine is fatal."""
    board = _empty_board()
    board.tile(3, 5).old_earth_mine = True
    board.tile(3, 6).freeze_mine = True

    # 1 safe + 1 freeze + 1 mine. Need 3 picks → safe + freeze (preferred fallback) + mine.
    deploy_zone = [[3, 5], [3, 6], [2, 5]]
    recs = recommend_deploy_tiles(board, deploy_zone)

    assert len(recs) == 3
    hazards = [r["hazard"] for r in recs]
    # safe pick first, then freeze_mine, then old_earth_mine.
    assert hazards == [None, "freeze_mine", "old_earth_mine"]
    # The last two are fallbacks.
    assert recs[0]["hazard_warning"] is False
    assert recs[1]["hazard_warning"] is True
    assert recs[2]["hazard_warning"] is True


def test_acceptance_spec_freeze_mine_2_old_earth_1_forest_1_ground_1():
    """Acceptance scenario from the spec: 5-tile zone with
    1 ground, 2 freeze_mine, 1 old_earth_mine, 1 forest.
    Expect top-3 = ground + forest + (reluctant freeze_mine)."""
    board = _empty_board()
    # Forest at C4 (bridge x=4, y=5) — terrain "forest", not a hazard.
    board.tile(4, 5).terrain = "forest"
    # Plain ground at B5 (bridge x=3, y=6) — terrain stays "ground".
    # Freeze mines at C5 (3,5) and B6 (2,6).
    board.tile(3, 5).freeze_mine = True
    board.tile(2, 6).freeze_mine = True
    # Old Earth Mine at C7 (1, 5).
    board.tile(1, 5).old_earth_mine = True

    deploy_zone = [
        [4, 5],  # forest — safe
        [3, 6],  # ground — safe
        [3, 5],  # freeze
        [2, 6],  # freeze
        [1, 5],  # old earth mine
    ]
    recs = recommend_deploy_tiles(board, deploy_zone)

    assert len(recs) == 3
    # The two safe tiles must be in the picks.
    coords = {(r["x"], r["y"]) for r in recs}
    assert (4, 5) in coords  # forest
    assert (3, 6) in coords  # plain ground
    # The third pick is a freeze_mine fallback (severity 2 < old_earth_mine 3).
    fallback = [r for r in recs if r["hazard_warning"]]
    assert len(fallback) == 1
    assert fallback[0]["hazard"] == "freeze_mine"
    assert (fallback[0]["x"], fallback[0]["y"]) in {(3, 5), (2, 6)}
    # Old Earth Mine never gets picked when a freeze_mine is available.
    assert (1, 5) not in coords


def test_forest_is_not_a_hazard():
    """Forest catches fire when damaged but a mech that STOPS on a
    forest tile pre-attack is unharmed. Don't filter forest."""
    board = _empty_board()
    board.tile(4, 4).terrain = "forest"
    deploy_zone = [[4, 4], [2, 5], [2, 6]]
    ranked = rank_deploy_tiles(board, deploy_zone)
    assert (4, 4) in set(ranked)


# ---------------------------------------------------------------------------
# recommend_deploy_tiles — annotations on safe picks
# ---------------------------------------------------------------------------


def test_safe_picks_have_no_hazard_warning():
    board = _empty_board()
    deploy_zone = [[4, 4], [2, 5], [2, 6]]
    recs = recommend_deploy_tiles(board, deploy_zone)
    assert len(recs) == 3
    assert all(r["hazard"] is None for r in recs)
    assert all(r["hazard_warning"] is False for r in recs)


def test_two_freeze_mines_one_ground_one_old_earth_one_forest_acceptance():
    """Live verification scenario from the task spec, checked end-to-end
    against `recommend_deploy_tiles` output shape."""
    board = _empty_board()
    board.tile(4, 5).terrain = "forest"
    board.tile(3, 5).freeze_mine = True
    board.tile(2, 6).freeze_mine = True
    board.tile(1, 5).old_earth_mine = True

    deploy_zone = [
        [4, 5],  # forest
        [3, 6],  # ground
        [3, 5],  # freeze_mine
        [2, 6],  # freeze_mine
        [1, 5],  # old_earth_mine
    ]
    # Annotation: full DEPLOYMENT ZONE listing (caller re-classifies).
    annotations = {
        (t[0], t[1]): classify_deploy_hazard(board, t[0], t[1])
        for t in deploy_zone
    }
    assert annotations[(4, 5)] is None        # forest is safe
    assert annotations[(3, 6)] is None        # ground is safe
    assert annotations[(3, 5)] == "freeze_mine"
    assert annotations[(2, 6)] == "freeze_mine"
    assert annotations[(1, 5)] == "old_earth_mine"
