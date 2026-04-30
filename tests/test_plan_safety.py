from src.solver.plan_safety import audit_plan_safety, plan_requires_safety_block


def _summary(grid=7, buildings=8, hp=14):
    return {
        "grid_power": grid,
        "buildings_alive": buildings,
        "building_hp_total": hp,
    }


def test_clean_plan_is_not_blocked():
    audit = audit_plan_safety(
        _summary(grid=7, buildings=8, hp=14),
        _summary(grid=7, buildings=8, hp=14),
    )

    assert audit["status"] == "CLEAN"
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is False


def test_predicted_grid_loss_blocks_plan():
    audit = audit_plan_safety(
        _summary(grid=7, buildings=8, hp=14),
        _summary(grid=6, buildings=8, hp=14),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "grid_damage"


def test_partial_building_hp_loss_blocks_even_without_grid_drop():
    audit = audit_plan_safety(
        _summary(grid=7, buildings=8, hp=14),
        _summary(grid=7, buildings=8, hp=13),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert [v["kind"] for v in audit["violations"]] == ["building_hp_loss"]


def test_destroyed_building_blocks_plan():
    audit = audit_plan_safety(
        _summary(grid=7, buildings=8, hp=14),
        _summary(grid=7, buildings=7, hp=13),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert {v["kind"] for v in audit["violations"]} == {
        "building_destroyed",
        "building_hp_loss",
    }


def test_allow_dirty_plan_overrides_block():
    audit = audit_plan_safety(
        _summary(grid=7, buildings=8, hp=14),
        _summary(grid=6, buildings=8, hp=14),
    )

    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is False


def test_missing_comparable_fields_is_unknown_not_blocked():
    audit = audit_plan_safety({}, {})

    assert audit["status"] == "UNKNOWN"
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is False
