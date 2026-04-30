from __future__ import annotations

from dataclasses import dataclass

from src.solver.action_classification import action_has_attack, is_board_target


@dataclass
class _Action:
    weapon: str | None
    target: tuple[int, int] | None


def test_valid_weapon_and_board_target_is_attack():
    assert action_has_attack(_Action("Prime_Punchmech", (2, 3))) is True


def test_support_wind_target_zone_is_attack():
    assert action_has_attack(_Action("Support_Wind", (1, 3))) is True


def test_unknown_weapon_with_sentinel_target_is_not_attack():
    assert action_has_attack(_Action("Unknown", (255, 255))) is False


def test_none_weapon_with_valid_target_is_not_attack():
    assert action_has_attack(_Action("None", (2, 3))) is False


def test_repair_is_not_attack():
    assert action_has_attack(_Action("_REPAIR", (2, 3))) is False


def test_off_board_target_is_not_attack():
    assert is_board_target((8, 0)) is False
    assert action_has_attack(_Action("Prime_Punchmech", (255, 255))) is False
