from src.model.weapons import get_weapon_def


def test_snowtank_mark_i_weapon_def_matches_lua_projectile_fire():
    w = get_weapon_def("SnowtankAtk1")

    assert w is not None
    assert w.name == "Cannon 8R Mark I"
    assert w.weapon_type == "projectile"
    assert w.damage == 1
    assert w.range_max == 0
    assert w.fire is True
