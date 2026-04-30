"""Regression tests for the Detritus Digger research gates."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.model.pawn_stats import get_pawn_stats
from src.solver import unknown_detector


def _fake_board(unit_types):
    units = [
        SimpleNamespace(type=t, weapon="", weapon2="", is_mech=False)
        for t in unit_types
    ]
    tiles = [[SimpleNamespace(terrain="ground") for _ in range(8)] for _ in range(8)]
    return SimpleNamespace(units=units, tiles=tiles)


def test_known_types_catalogs_digger_and_rock_wall():
    repo_root = Path(__file__).parent.parent
    with open(repo_root / "data" / "known_types.json") as f:
        known = json.load(f)
    observed = set(known["observed_pawn_types"])
    for pawn_type in ("Digger1", "Digger2", "Wall"):
        assert pawn_type in observed


def test_digger_and_wall_do_not_trigger_research_gate():
    unknown_detector.reset_cache()
    board = _fake_board(["Digger1", "Digger2", "Wall"])
    unknowns = unknown_detector.detect_unknowns(board)
    assert unknowns["types"] == []


def test_digger_and_wall_have_static_stats():
    d1 = get_pawn_stats("Digger1")
    d2 = get_pawn_stats("Digger2")
    wall = get_pawn_stats("Wall")
    assert d1.move_speed == 3
    assert d2.move_speed == 3
    assert wall.move_speed == 0
    assert wall.pushable is True
