"""Unit tests for hazard-tile filtering in rank_deploy_tiles.

Detritus / Disposal Vault missions can include CONVEYOR BELTS in the deploy
zone. Clicking a conveyor tile to deploy a mech results in the conveyor
immediately pushing the mech off (sometimes off the deploy zone entirely),
forcing a retry. Same problem with TELEPORTER PADS on disposal missions.

`rank_deploy_tiles` should drop both of those tile types from the ranked
recommendation list. The full `deployment_zone` printed by `read` still
includes them so the user can manually override.
"""

from __future__ import annotations

from src.loop.commands import rank_deploy_tiles
from src.model.board import Board


def _empty_board() -> Board:
    """Plain 8x8 ground board with no units, no enemies, no buildings."""
    return Board()


def test_conveyor_tiles_excluded_from_ranking():
    """A conveyor tile in the deploy zone must not appear in the ranked list."""
    board = _empty_board()
    # Mark C5 (bridge x=3, y=5) and B5 (bridge x=3, y=6) as conveyor belts —
    # this mirrors the Disposal Vault failure mode the user observed today.
    board.tile(3, 5).conveyor = 0  # right
    board.tile(3, 6).conveyor = 1  # down

    deploy_zone = [
        [3, 5],  # C5 — conveyor
        [3, 6],  # B5 — conveyor
        [2, 5],  # C6 — plain ground
        [2, 6],  # B6 — plain ground
        [1, 5],  # C7 — plain ground (rank_deploy_tiles requires forward tile)
    ]

    ranked = rank_deploy_tiles(board, deploy_zone)
    ranked_set = set(ranked)

    assert (3, 5) not in ranked_set, "C5 conveyor leaked into ranked deploy"
    assert (3, 6) not in ranked_set, "B5 conveyor leaked into ranked deploy"
    # The plain-ground tiles should be available to pick from.
    assert ranked_set.issubset({(2, 5), (2, 6), (1, 5)})


def test_teleporter_pads_excluded_from_ranking():
    """Teleporter pad endpoints must not appear in the ranked list."""
    board = _empty_board()
    # Pair endpoints at (3, 5) and (5, 5).
    board.teleporter_pairs = [(3, 5, 5, 5)]

    deploy_zone = [
        [3, 5],  # pad endpoint A
        [5, 5],  # pad endpoint B
        [2, 5],  # plain
        [2, 6],  # plain
        [4, 4],  # plain (forward row)
    ]

    ranked = rank_deploy_tiles(board, deploy_zone)
    ranked_set = set(ranked)

    assert (3, 5) not in ranked_set
    assert (5, 5) not in ranked_set
    assert ranked_set.issubset({(2, 5), (2, 6), (4, 4)})


def test_plain_tiles_still_ranked_when_some_are_conveyors():
    """Filter is non-destructive — plain tiles still get picked normally."""
    board = _empty_board()
    board.tile(3, 5).conveyor = 0

    deploy_zone = [
        [3, 5],  # conveyor
        [4, 4],  # plain, forward row
        [2, 5],  # plain
        [2, 6],  # plain
    ]
    ranked = rank_deploy_tiles(board, deploy_zone)

    assert (3, 5) not in ranked
    # We expect 3 picks from the 3 plain tiles.
    assert len(ranked) == 3
    assert set(ranked) == {(4, 4), (2, 5), (2, 6)}


def test_no_filter_when_no_hazards():
    """Sanity: with neither conveyors nor pads, ranking is unchanged."""
    board = _empty_board()
    deploy_zone = [
        [4, 4],
        [2, 5],
        [2, 6],
        [3, 5],
    ]
    ranked = rank_deploy_tiles(board, deploy_zone)
    # All four are valid candidates, ranker picks 3.
    assert len(ranked) == 3
    assert set(ranked).issubset({(4, 4), (2, 5), (2, 6), (3, 5)})
