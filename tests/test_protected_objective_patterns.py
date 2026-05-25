"""Tests for protected-unit summary pattern resolution."""
from __future__ import annotations

from types import SimpleNamespace

from src.loop.commands import _protected_objective_patterns


def test_bridge_bonus_objective_unit_types_count_as_protected():
    board = SimpleNamespace(
        mission_id="Mission_Belt",
        protect_objective_unit_types=[],
    )
    bridge_data = {
        "mission_id": "Mission_Belt",
        "bonus_objective_unit_types": ["GlowingScorpion"],
    }

    assert _protected_objective_patterns(board, bridge_data) == ["GlowingScorpion"]


def test_live_volatile_mission_metadata_counts_as_protected():
    board = SimpleNamespace(
        mission_id="Mission_Volatile",
        protect_objective_unit_types=[],
    )

    patterns = _protected_objective_patterns(board, {"mission_id": "Mission_Volatile"})

    assert "GlowingScorpion" in patterns
    assert "Volatile_Vek" in patterns
