from src.solver.plan_safety import audit_plan_safety, plan_requires_safety_block


def _summary(grid=7, buildings=8, hp=14, **extra):
    data = {
        "grid_power": grid,
        "buildings_alive": buildings,
        "building_hp_total": hp,
    }
    data.update(extra)
    return data


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


def test_predicted_mech_loss_blocks_plan():
    audit = audit_plan_safety(
        _summary(mechs_alive=3),
        _summary(mechs_alive=2),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "mech_lost"


def test_predicted_mech_on_lethal_danger_blocks_plan():
    audit = audit_plan_safety(
        _summary(mechs_on_danger=[]),
        _summary(mechs_on_danger=[
            {"uid": 7, "type": "TeleMech", "pos": [2, 5]},
        ]),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "mech_on_danger"


def test_newly_disabled_mech_blocks_plan():
    audit = audit_plan_safety(
        _summary(mechs_disabled=[]),
        _summary(mechs_disabled=[
            {"uid": 1, "type": "IceMech", "reasons": ["frozen"]},
        ]),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "mech_disabled"


def test_mech_hp_loss_warns_without_blocking():
    audit = audit_plan_safety(
        _summary(mech_hp_total=7),
        _summary(mech_hp_total=6),
    )

    assert audit["status"] == "WARN"
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is False
    assert audit["violations"][0]["kind"] == "mech_hp_loss"


def test_uncollected_pod_loss_blocks_plan():
    audit = audit_plan_safety(
        _summary(pods_present=1),
        _summary(pods_present=0, pods_collected=0),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "pod_lost"


def test_collected_pod_drop_is_clean():
    audit = audit_plan_safety(
        _summary(pods_present=1),
        _summary(pods_present=0, pods_collected=1),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False
