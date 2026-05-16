from src.model.weapons import get_weapon_def


def test_snowtank_mark_i_weapon_def_matches_lua_projectile_fire():
    w = get_weapon_def("SnowtankAtk1")

    assert w is not None
    assert w.name == "Cannon 8R Mark I"
    assert w.weapon_type == "projectile"
    assert w.damage == 1
    assert w.range_max == 0
    assert w.fire is True


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
