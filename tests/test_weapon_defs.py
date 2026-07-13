import json
from pathlib import Path
from types import SimpleNamespace

from src.model.pawn_stats import get_pawn_stats
from src.model.weapons import get_weapon_def
from src.solver import unknown_detector


def test_snowtank_mark_i_weapon_def_matches_lua_projectile_fire():
    w = get_weapon_def("SnowtankAtk1")

    assert w is not None
    assert w.name == "Cannon 8R Mark I"
    assert w.weapon_type == "projectile"
    assert w.damage == 1
    assert w.range_max == 0
    assert w.fire is True


def test_hacking_cannon_bot_player_aliases_match_mark_i():
    known = json.loads(Path("data/known_types.json").read_text())
    w = get_weapon_def("SnowtankAtk1_Player")

    assert "Snowtank1_Player" in known["observed_pawn_types"]
    assert "SnowtankAtk1_Player" in known["observed_weapons"]
    assert w is not None
    assert w.name == "Cannon 8R Mark I"
    assert w.weapon_type == "projectile"
    assert w.damage == 1
    assert w.range_max == 0
    assert w.fire is True
    assert get_pawn_stats("Snowtank1_Player").move_speed == 3
    assert (
        get_pawn_stats("Snowtank1_Player").default_weapon
        == "SnowtankAtk1_Player"
    )


def test_dung_attack_aliases_match_tumblebug_weapon_defs():
    normal = get_weapon_def("DungAtk1")
    alpha = get_weapon_def("DungAtk2")

    assert normal is not None
    assert normal.name == "Tumblebug Boulder"
    assert normal.weapon_type == "melee"
    assert normal.damage == 1
    assert alpha is not None
    assert alpha.name == "Alpha Tumblebug Boulder"
    assert alpha.weapon_type == "melee"
    assert alpha.damage == 3


def test_smoldering_shells_upgrade_weapon_defs():
    base = get_weapon_def("Ranged_SmokeFire")
    more_smoke = get_weapon_def("Ranged_SmokeFire_A")
    damage = get_weapon_def("Ranged_SmokeFire_B")
    both = get_weapon_def("Ranged_SmokeFire_AB")

    assert base is not None
    assert more_smoke is not None
    assert damage is not None
    assert both is not None
    assert base.damage == 1
    assert more_smoke.damage == 1
    assert damage.damage == 3
    assert both.damage == 3
    assert more_smoke.upgrade_a == "more smoke"


def test_techno_hornet_needle_shot_defs_and_fallback_stats():
    known = json.loads(Path("data/known_types.json").read_text())
    expected = {
        "Vek_Hornet": (1, 1),
        "Vek_Hornet_A": (2, 2),
        "Vek_Hornet_B": (2, 2),
        "Vek_Hornet_AB": (3, 3),
    }

    for weapon_id, (damage, range_max) in expected.items():
        weapon = get_weapon_def(weapon_id)
        assert weapon is not None
        assert weapon.name == "Needle Shot"
        assert weapon.weapon_type == "melee"
        assert weapon.damage == damage
        assert weapon.push == "forward"
        assert weapon.range_max == range_max
        assert weapon.path_size == range_max

    assert "VekHornet" in known["weapon_enum"]
    assert "VekHornetAB" in known["weapon_enum"]
    assert "Vek_Hornet" in known["observed_weapons"]
    stats = get_pawn_stats("HornetMech")
    assert stats.move_speed == 4
    assert stats.flying is True
    assert stats.massive is True
    assert stats.class_type == "TechnoVek"
    assert stats.default_weapon == "Vek_Hornet"


def test_techno_hornet_needle_shot_does_not_trigger_unknown_gate():
    unknown_detector.reset_cache()
    board = SimpleNamespace(
        units=[SimpleNamespace(
            type="HornetMech",
            weapon="Vek_Hornet",
            weapon2="",
            is_mech=True,
        )],
        tiles=[
            [SimpleNamespace(terrain="ground") for _ in range(8)]
            for _ in range(8)
        ],
    )

    unknowns = unknown_detector.detect_unknowns(board, phase="combat_player")

    assert unknowns == {
        "types": [],
        "terrain_ids": [],
        "weapons": [],
        "screens": [],
    }


def test_arachnophiles_catalog_entries_match_observed_lua_ids():
    known = json.loads(Path("data/known_types.json").read_text())

    assert {
        "Brute_TC_Ricochet",
        "Ranged_Arachnoid",
        "Science_MassShift",
        "Science_TC_SwapOther",
        "DeployUnit_AracnoidAtk",
    } <= set(known["observed_weapons"])
    assert {"DeployUnit_Aracnoid", "DeployUnit_AracnoidB"} <= set(
        known["observed_pawn_types"]
    )

    ricochet = get_weapon_def("Brute_TC_Ricochet")
    assert ricochet is not None
    assert ricochet.name == "Ricochet Rocket"
    assert ricochet.weapon_type == "two_click"
    assert ricochet.damage == 1
    assert ricochet.push == "forward"

    injector = get_weapon_def("Ranged_Arachnoid")
    assert injector is not None
    assert injector.name == "Arachnoid Injector"
    assert injector.weapon_type == "artillery"
    assert injector.damage == 1
    assert injector.spawns == "DeployUnit_Aracnoid"
    assert get_weapon_def("Ranged_Arachnoid_B").spawns == "DeployUnit_AracnoidB"
    assert get_weapon_def("DeployUnit_AracnoidAtk").push == "forward"
    assert get_weapon_def("DeployUnit_AracnoidAtkB").acid is True

    shift = get_weapon_def("Science_MassShift")
    assert shift is not None
    assert shift.name == "Area Shift"
    assert shift.weapon_type == "self_aoe"
    assert shift.push == "forward"
    assert shift.targets_allies is True

    force_swap = get_weapon_def("Science_TC_SwapOther")
    assert force_swap is not None
    assert force_swap.name == "Force Swap"
    assert force_swap.weapon_type == "two_click"

    bomb_two = get_weapon_def("Ranged_DeployBomb_A")
    assert bomb_two is not None
    assert "Ranged_DeployBomb_A" in known["observed_weapons"]
    assert bomb_two.name == "Bomb Dispenser"
    assert bomb_two.weapon_type == "two_click"
    assert bomb_two.spawns == "DeployUnit_Bomby"

    assert get_pawn_stats("BulkMech").default_weapon == "Brute_TC_Ricochet"
    assert get_pawn_stats("BulkMech").class_type == "Brute"
    assert get_pawn_stats("ScorpioMech").default_weapon == "Ranged_Arachnoid"
    assert get_pawn_stats("ScorpioMech").class_type == "Ranged"
    assert get_pawn_stats("FourwayMech").default_weapon == "Science_MassShift"
    assert get_pawn_stats("FourwayMech").move_speed == 4
    assert get_pawn_stats("ExchangeMech").default_weapon == "Science_TC_SwapOther"
    assert get_pawn_stats("ExchangeMech").class_type == "Science"
    assert get_pawn_stats("DeployUnit_Aracnoid").default_weapon == "DeployUnit_AracnoidAtk"
    assert get_pawn_stats("DeployUnit_Aracnoid").move_speed == 3
