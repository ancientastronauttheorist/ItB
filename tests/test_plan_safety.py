from src.solver.plan_safety import (
    audit_plan_safety,
    final_cave_emergency_pylon_loss_allowed,
    final_cave_resist_gamble_allowed,
    plan_requires_safety_block,
    safety_loss_profile,
)


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


def test_allow_dirty_plan_does_not_override_timeline_collapse():
    audit = audit_plan_safety(
        _summary(grid=1, buildings=8, hp=14),
        _summary(grid=0, buildings=8, hp=14),
    )

    kinds = [v["kind"] for v in audit["violations"]]
    assert "grid_damage" in kinds
    assert "grid_timeline_collapse" in kinds
    assert safety_loss_profile(audit)["label"] == "timeline_collapse"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_timeline_collapse_requires_explicit_debug_escape():
    audit = audit_plan_safety(
        _summary(grid=1, buildings=8, hp=14),
        _summary(grid=0, buildings=8, hp=14),
    )

    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_timeline_collapse_debug=True,
    ) is False


def test_final_cave_resist_gamble_can_be_dirty_consented_on_last_turn():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            turn=4,
            total_turns=4,
            grid=4,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
        _summary(
            mission_id="Mission_Final_Cave",
            turn=4,
            total_turns=4,
            grid=0,
            buildings=4,
            hp=8,
            pylons_alive=4,
            pylon_hp_total=8,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
    )

    assert final_cave_resist_gamble_allowed(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is False


def test_final_cave_resist_gamble_rejects_before_last_turn():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            turn=3,
            total_turns=4,
            grid=4,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
        _summary(
            mission_id="Mission_Final_Cave",
            turn=3,
            total_turns=4,
            grid=0,
            buildings=4,
            hp=8,
            pylons_alive=4,
            pylon_hp_total=8,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
    )

    assert final_cave_resist_gamble_allowed(audit) is False
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_cave_resist_gamble_rejects_bomb_loss():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            turn=4,
            total_turns=4,
            grid=4,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
        _summary(
            mission_id="Mission_Final_Cave",
            turn=4,
            total_turns=4,
            grid=0,
            buildings=4,
            hp=8,
            pylons_alive=4,
            pylon_hp_total=8,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=False,
        ),
    )

    assert final_cave_resist_gamble_allowed(audit) is False
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_cave_pylon_loss_is_named():
    audit = audit_plan_safety(
        _summary(
            grid=4,
            buildings=7,
            hp=14,
            pylons_alive=7,
            pylon_hp_total=14,
        ),
        _summary(
            grid=3,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
        ),
    )

    kinds = {v["kind"] for v in audit["violations"]}
    assert {"pylon_destroyed", "pylon_hp_loss"} <= kinds
    assert safety_loss_profile(audit)["label"] == "pylon_loss"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_cave_emergency_pylon_loss_can_be_dirty_consented():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            grid=6,
            buildings=7,
            hp=14,
            pylons_alive=7,
            pylon_hp_total=14,
            mechs_alive=3,
            mech_hp_total=10,
            bigbomb_alive=True,
        ),
        _summary(
            mission_id="Mission_Final_Cave",
            grid=4,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
            mechs_alive=3,
            mech_hp_total=10,
            bigbomb_alive=True,
        ),
    )

    assert final_cave_emergency_pylon_loss_allowed(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is False


def test_final_cave_emergency_pylon_loss_rejects_mech_hp_debt():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            grid=6,
            buildings=7,
            hp=14,
            pylons_alive=7,
            pylon_hp_total=14,
            mechs_alive=3,
            mech_hp_total=10,
            bigbomb_alive=True,
        ),
        _summary(
            mission_id="Mission_Final_Cave",
            grid=4,
            buildings=6,
            hp=12,
            pylons_alive=6,
            pylon_hp_total=12,
            mechs_alive=3,
            mech_hp_total=9,
            bigbomb_alive=True,
        ),
    )

    assert final_cave_emergency_pylon_loss_allowed(audit) is False
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_allow_dirty_plan_does_not_override_protected_objective_loss():
    audit = audit_plan_safety(
        _summary(protected_objective_units_alive=2),
        _summary(protected_objective_units_alive=1),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "protected_objective_unit_lost"


def test_freezebots_protected_unit_unfreeze_blocks_plan():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FreezeBots",
            protected_objective_units_alive=2,
            protected_objective_units_frozen=2,
        ),
        _summary(
            mission_id="Mission_FreezeBots",
            protected_objective_units_alive=2,
            protected_objective_units_frozen=1,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "protected_objective_unit_unfrozen"


def test_missing_comparable_fields_is_unknown_and_blocks():
    audit = audit_plan_safety({}, {})

    assert audit["status"] == "UNKNOWN"
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(None) is True


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


def test_new_acid_mech_blocks_plan():
    audit = audit_plan_safety(
        _summary(mechs_acid=[]),
        _summary(mechs_acid=[
            {"uid": 1, "type": "RocketMech", "pos": [5, 6]},
        ]),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "mech_acid"
    assert safety_loss_profile(audit)["label"] == "mech_disabled"


def test_existing_acid_mech_does_not_block_again():
    acid_mech = {"uid": 1, "type": "RocketMech", "pos": [5, 6]}
    audit = audit_plan_safety(
        _summary(mechs_acid=[acid_mech]),
        _summary(mechs_acid=[acid_mech]),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_new_fire_and_web_warn_by_default_but_can_block_for_hard_target():
    fire = {"uid": 1, "type": "JetMech", "pos": [2, 3]}
    web = {"uid": 2, "type": "PulseMech", "pos": [4, 4]}
    audit = audit_plan_safety(
        _summary(mechs_fire=[], mechs_webbed=[]),
        _summary(mechs_fire=[fire], mechs_webbed=[web]),
    )

    assert audit["status"] == "WARN"
    assert plan_requires_safety_block(audit) is False
    assert {v["kind"] for v in audit["violations"]} == {
        "mech_fire",
        "mech_webbed",
    }

    hard_audit = audit_plan_safety(
        _summary(mechs_fire=[], mechs_webbed=[]),
        _summary(mechs_fire=[fire], mechs_webbed=[web]),
        block_mech_status_loss=True,
    )
    assert hard_audit["status"] == "DIRTY"
    assert plan_requires_safety_block(hard_audit) is True


def test_predicted_bigbomb_loss_blocks_plan():
    audit = audit_plan_safety(
        _summary(bigbomb_alive=True),
        _summary(bigbomb_alive=False),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "bigbomb_lost"


def test_mech_hp_loss_warns_without_blocking():
    audit = audit_plan_safety(
        _summary(mech_hp_total=7),
        _summary(mech_hp_total=6),
    )

    assert audit["status"] == "WARN"
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is False
    assert audit["violations"][0]["kind"] == "mech_hp_loss"


def test_mech_hp_loss_blocks_for_perfect_battle_mode():
    audit = audit_plan_safety(
        _summary(mech_hp_total=10),
        _summary(mech_hp_total=8),
        block_mech_hp_loss=True,
    )

    assert audit["status"] == "DIRTY"
    assert audit["blocking"] is True
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "mech_hp_loss"
    assert audit["violations"][0]["blocking"] is True
    assert safety_loss_profile(audit)["label"] == "mech_hp_loss"


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


def test_safety_loss_profile_names_grid_tradeoff():
    audit = audit_plan_safety(
        _summary(grid=4, buildings=8, hp=10, mechs_alive=3),
        _summary(grid=3, buildings=8, hp=9, mechs_alive=3),
    )

    profile = safety_loss_profile(audit)

    assert profile["label"] == "grid_loss"
    assert profile["blocking"] is True
    assert profile["losses"]["grid_power"] == 1
    assert profile["losses"]["building_hp_total"] == 1


def test_safety_loss_profile_names_mech_tradeoff():
    audit = audit_plan_safety(
        _summary(grid=4, buildings=8, hp=10, mechs_alive=3),
        _summary(grid=4, buildings=8, hp=9, mechs_alive=2),
    )

    profile = safety_loss_profile(audit)

    assert profile["label"] == "mech_loss"
    assert profile["losses"]["building_hp_total"] == 1
    assert profile["losses"]["mechs_alive"] == 1
