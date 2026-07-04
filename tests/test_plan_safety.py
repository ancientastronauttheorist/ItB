from src.solver.plan_safety import (
    audit_plan_safety,
    final_bomb_dirty_consent_allowed,
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


def test_final_bomb_turn_can_dirty_consent_bonus_building_loss():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Bomb",
            turn=4,
            total_turns=4,
            grid=7,
            buildings=7,
            hp=9,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            protected_objective_units_alive=2,
            mechs_alive=3,
            mech_hp_total=7,
        ),
        _summary(
            mission_id="Mission_Bomb",
            turn=4,
            total_turns=4,
            grid=6,
            buildings=6,
            hp=8,
            objective_buildings_alive=0,
            objective_building_hp_total=0,
            protected_objective_units_alive=2,
            mechs_alive=3,
            mech_hp_total=7,
            mechs_acid=[],
            mechs_fire=[],
            mechs_webbed=[],
            mechs_on_danger=[],
            mechs_disabled=[],
        ),
    )

    assert final_bomb_dirty_consent_allowed(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is False


def test_final_bomb_turn_rejects_bomb_loss():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Bomb",
            turn=4,
            total_turns=4,
            grid=7,
            buildings=7,
            hp=9,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            protected_objective_units_alive=2,
            mechs_alive=3,
        ),
        _summary(
            mission_id="Mission_Bomb",
            turn=4,
            total_turns=4,
            grid=6,
            buildings=6,
            hp=8,
            objective_buildings_alive=0,
            objective_building_hp_total=0,
            protected_objective_units_alive=1,
            mechs_alive=3,
        ),
    )

    assert final_bomb_dirty_consent_allowed(audit) is False
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_turn_objective_building_target_blocks_without_hp_loss():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Repair",
            turn=3,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Repair",
            turn=4,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
            objective_building_targets=[{
                "uid": 106,
                "type": "Moth1",
                "pos": [6, 2],
                "target": [4, 2],
            }],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "objective_building_targeted_final"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_turn_objective_target_is_clean_after_safe_enemy_phase_projection():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Artillery",
            turn=4,
            total_turns=4,
            grid=6,
            buildings=7,
            hp=9,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
        ),
        _summary(
            mission_id="Mission_Artillery",
            turn=5,
            total_turns=4,
            grid=6,
            buildings=7,
            hp=9,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
            objective_building_targets=[{
                "uid": 672,
                "type": "Burnbug1",
                "pos": [6, 4],
                "target": [5, 5],
            }],
            buildings_destroyed_by_enemies=0,
            enemies_killed_by_enemy_phase=0,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert not any(
        v["kind"] == "objective_building_targeted_final"
        for v in audit["violations"]
    )
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is False


def test_final_turn_objective_target_still_blocks_before_post_mission_projection():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Repair",
            turn=3,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Repair",
            turn=4,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
            objective_building_targets=[{
                "uid": 106,
                "type": "Moth1",
                "pos": [6, 2],
                "target": [4, 2],
            }],
            buildings_destroyed_by_enemies=0,
            enemies_killed_by_enemy_phase=0,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "objective_building_targeted_final"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_nonfinal_objective_building_target_is_not_terminal():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Repair",
            turn=2,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Repair",
            turn=3,
            total_turns=4,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
        ),
    )

    assert audit["status"] == "CLEAN"


def test_penultimate_infinite_spawn_objective_building_target_is_not_terminal():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Solar",
            turn=3,
            total_turns=4,
            is_infinite_spawn=True,
            objective_buildings_alive=2,
            objective_building_hp_total=2,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Solar",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            objective_buildings_alive=2,
            objective_building_hp_total=2,
            objective_buildings_targeted=1,
            objective_building_targets=[{
                "uid": 798,
                "type": "Jelly_Explode1",
                "pos": [6, 2],
                "target": [4, 3],
            }],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert not any(
        v["kind"] == "objective_building_targeted_final"
        for v in audit["violations"]
    )


def test_spawn_points_keep_objective_target_recoverable():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Barrels",
            turn=3,
            total_turns=4,
            remaining_spawns=0,
            spawn_points=2,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Barrels",
            turn=4,
            total_turns=4,
            remaining_spawns=0,
            objective_buildings_alive=1,
            objective_building_hp_total=1,
            objective_buildings_targeted=1,
        ),
    )

    assert audit["status"] == "CLEAN"


def test_final_infinite_spawn_objective_building_target_blocks():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Solar",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            objective_buildings_alive=2,
            objective_building_hp_total=2,
            objective_buildings_targeted=0,
        ),
        _summary(
            mission_id="Mission_Solar",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            objective_buildings_alive=2,
            objective_building_hp_total=2,
            objective_buildings_targeted=1,
            objective_building_targets=[{
                "uid": 798,
                "type": "Jelly_Explode1",
                "pos": [6, 2],
                "target": [4, 3],
            }],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "objective_building_targeted_final"


def test_final_cave_resist_gamble_rejects_before_last_turn():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Final_Cave",
            turn=2,
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
            turn=2,
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


def test_explicit_stress_flag_overrides_protected_objective_loss():
    audit = audit_plan_safety(
        _summary(protected_objective_units_alive=2),
        _summary(protected_objective_units_alive=1),
    )

    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_protected_objective_loss_dirty=True,
    ) is False


def test_dirty_allowances_compose_for_pod_and_protected_objective_loss():
    audit = audit_plan_safety(
        _summary(protected_objective_units_alive=2, pods_present=1),
        _summary(protected_objective_units_alive=1, pods_present=0),
    )

    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_pod_loss_dirty=True,
    ) is True
    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_pod_loss_dirty=True,
        allow_protected_objective_loss_dirty=True,
    ) is False


def test_objective_loss_stress_flag_overrides_objective_building_loss():
    audit = audit_plan_safety(
        _summary(objective_buildings_alive=1, objective_building_hp_total=1),
        _summary(objective_buildings_alive=0, objective_building_hp_total=0),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_objective_loss_dirty=True,
    ) is False


def test_final_turn_destroy_objective_unit_alive_blocks():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_AcidStorm",
            turn=4,
            total_turns=4,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "Storm_Generator", "alive": True}],
        ),
        _summary(
            mission_id="Mission_AcidStorm",
            turn=4,
            total_turns=4,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "Storm_Generator", "alive": True}],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "destroy_objective_unit_alive_final"


def test_penultimate_infinite_spawn_destroy_objective_unit_alive_does_not_block():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_BlobberBoss",
            turn=3,
            total_turns=4,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BlobberBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_BlobberBoss",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BlobberBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert not any(
        v["kind"] == "destroy_objective_unit_alive_final"
        for v in audit["violations"]
    )
    assert audit["blocking"] is False
    assert plan_requires_safety_block(audit) is False


def test_penultimate_turn_with_future_spawns_does_not_final_block_destroy_objective():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=3,
            total_turns=4,
            remaining_spawns=1,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=1,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert audit["blocking"] is False


def test_final_infinite_spawn_destroy_objective_unit_alive_blocks():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_BlobberBoss",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BlobberBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_BlobberBoss",
            turn=4,
            total_turns=4,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BlobberBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "destroy_objective_unit_alive_final"


def test_infinite_spawn_remaining_spawn_signal_does_not_relax_hq_objective_gate():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_BurnbugBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=1,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BurnbugBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_BurnbugBoss",
            turn=5,
            total_turns=4,
            remaining_spawns=1,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BurnbugBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "destroy_objective_unit_alive_final"


def test_infinite_spawn_zero_remaining_spawns_still_blocks_destroy_objective_unit():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_BurnbugBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=0,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BurnbugBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_BurnbugBoss",
            turn=5,
            total_turns=4,
            remaining_spawns=0,
            is_infinite_spawn=True,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BurnbugBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "destroy_objective_unit_alive_final"


def test_visible_victory_counter_overrides_spawn_clock_for_destroy_objective():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=3,
            total_turns=4,
            remaining_spawns=0,
            victory_turns=2,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=0,
            victory_turns=1,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert audit["blocking"] is False


def test_infinite_spawn_current_victory_counter_overrides_turn_limit_for_destroy_objective():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_BouncerBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=1,
            is_infinite_spawn=True,
            victory_turns=2,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BouncerBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_BouncerBoss",
            turn=5,
            total_turns=4,
            remaining_spawns=1,
            is_infinite_spawn=True,
            victory_turns=1,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "BouncerBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert audit["blocking"] is False
    assert not any(
        v["kind"] == "destroy_objective_unit_alive_final"
        for v in audit["violations"]
    )


def test_penultimate_turn_without_future_spawns_final_blocks_destroy_objective():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=3,
            total_turns=4,
            remaining_spawns=0,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
        _summary(
            mission_id="Mission_FireflyBoss",
            turn=4,
            total_turns=4,
            remaining_spawns=0,
            destroy_objective_units_alive=1,
            destroy_objective_units=[{"type": "FireflyBoss", "alive": True}],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "destroy_objective_unit_alive_final"


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


def test_filler_protected_unit_webbed_blocks_plan():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Filler",
            protected_objective_units_alive=1,
            protected_objective_units_webbed=0,
            protected_objective_units=[
                {"type": "Filler_Pawn", "alive": True, "webbed": False},
            ],
        ),
        _summary(
            mission_id="Mission_Filler",
            protected_objective_units_alive=1,
            protected_objective_units_webbed=1,
            protected_objective_units=[
                {"type": "Filler_Pawn", "alive": True, "webbed": True},
            ],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "protected_objective_unit_webbed"


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
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_mech_loss_dirty=True,
    ) is False
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


def test_mech_damage_objective_limit_blocks_and_is_not_dirty_consentable():
    audit = audit_plan_safety(
        _summary(
            mech_hp_total=7,
            mech_damage_taken_total=3,
            mech_damage_objective_limit=4,
        ),
        _summary(
            mech_hp_total=6,
            mech_damage_taken_total=4,
            mech_damage_objective_limit=4,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["blocking"] is True
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert [v["kind"] for v in audit["violations"]] == [
        "mech_hp_loss",
        "mech_damage_objective_failed",
    ]
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_mech_damage_objective_allows_staying_below_limit():
    audit = audit_plan_safety(
        _summary(
            mech_hp_total=8,
            mech_damage_taken_total=2,
            mech_damage_objective_limit=4,
        ),
        _summary(
            mech_hp_total=7,
            mech_damage_taken_total=3,
            mech_damage_objective_limit=4,
        ),
    )

    assert audit["status"] == "WARN"
    assert audit["blocking"] is False
    assert [v["kind"] for v in audit["violations"]] == ["mech_hp_loss"]


def test_freeze_building_objective_blocks_final_under_target():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=4,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=5,
            freeze_buildings_thawed=2,
        ),
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=4,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=5,
            freeze_buildings_thawed=4,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "freeze_building_objective_failed"
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_freeze_building_objective_blocks_destroyed_target_before_final():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=2,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=5,
            freeze_buildings_thawed=2,
        ),
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=2,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=4,
            freeze_buildings_thawed=2,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "freeze_building_objective_failed"


def test_freeze_building_objective_allows_incomplete_nonfinal_progress():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=2,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=5,
            freeze_buildings_thawed=1,
        ),
        _summary(
            mission_id="Mission_FreezeBldg",
            turn=2,
            total_turns=4,
            freeze_building_target=5,
            freeze_buildings_alive=5,
            freeze_buildings_thawed=2,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_terraform_grass_objective_blocks_final_under_target():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Terraform",
            turn=4,
            total_turns=4,
            terraform_grass_remaining=2,
            terraform_grass_tiles=[[3, 3], [4, 3]],
        ),
        _summary(
            mission_id="Mission_Terraform",
            turn=4,
            total_turns=4,
            terraform_grass_remaining=1,
            terraform_grass_tiles=[[4, 3]],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "terraform_grass_objective_failed"
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_terraform_grass_objective_allows_incomplete_nonfinal_progress():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Terraform",
            turn=2,
            total_turns=4,
            terraform_grass_remaining=2,
        ),
        _summary(
            mission_id="Mission_Terraform",
            turn=2,
            total_turns=4,
            terraform_grass_remaining=1,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_mountain_objective_blocks_final_under_target():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Force",
            turn=4,
            total_turns=4,
            mission_mountain_target=2,
            mission_mountains_destroyed=0,
            mission_mountain_tiles=[
                {"pos": [2, 2], "hp": 1},
                {"pos": [4, 4], "hp": 2},
            ],
        ),
        _summary(
            mission_id="Mission_Force",
            turn=4,
            total_turns=4,
            mission_mountain_target=2,
            mission_mountains_destroyed=1,
            mission_mountains_planned=1,
            mission_mountain_tiles=[
                {"pos": [4, 4], "hp": 2},
            ],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "mountain_objective_failed"
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_mountain_objective_allows_final_target_met():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Force",
            turn=4,
            total_turns=4,
            mission_mountain_target=2,
            mission_mountains_destroyed=1,
        ),
        _summary(
            mission_id="Mission_Force",
            turn=4,
            total_turns=4,
            mission_mountain_target=2,
            mission_mountains_destroyed=2,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_mite_objective_blocks_final_infected_mech():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=1,
            mites_status_tracked=True,
            mechs_infected=[
                {"uid": 2, "type": "IgniteMech", "pos": [1, 4]},
            ],
        ),
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=1,
            mites_status_tracked=True,
            mechs_infected=[
                {"uid": 2, "type": "IgniteMech", "pos": [1, 4]},
            ],
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "mite_objective_failed"
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_mite_objective_conservatively_blocks_when_projection_loses_status():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=1,
            mites_status_tracked=True,
            mechs_infected=[
                {"uid": 2, "type": "IgniteMech", "pos": [1, 4]},
            ],
        ),
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=0,
            mites_status_tracked=False,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["predicted"] == 1
    assert audit["violations"][0]["details"]["predicted_status_tracked"] is False


def test_mite_objective_allows_final_clear():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=1,
            mites_status_tracked=True,
        ),
        _summary(
            mission_id="Mission_Holes",
            turn=4,
            total_turns=4,
            mites_remaining=0,
            mites_status_tracked=True,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_mite_objective_allows_final_clear_with_empty_projected_list():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Belt",
            turn=4,
            total_turns=4,
            mites_remaining=1,
            mites_status_tracked=True,
            mechs_infected=[
                {"uid": 2, "type": "PulseMech", "pos": [3, 1]},
            ],
        ),
        _summary(
            mission_id="Mission_Belt",
            turn=4,
            total_turns=4,
            mites_remaining=0,
            mites_status_tracked=False,
            mechs_infected=[],
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_final_turn_kill_objective_blocks_when_short():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_SnowStorm",
            turn=4,
            total_turns=4,
            mission_kill_target=5,
            mission_kills_done=4,
        ),
        _summary(
            mission_id="Mission_SnowStorm",
            turn=4,
            total_turns=4,
            mission_kill_target=5,
            mission_kills_done=4,
            mission_kills_planned=0,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "kill_objective_failed"
    assert audit["violations"][0]["details"] == {
        "target": 5,
        "planned_kills": 0,
    }
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_final_turn_acid_tank_kill_objective_blocks_when_short():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_AcidTank",
            turn=4,
            total_turns=4,
            mission_kill_target=4,
            mission_kills_done=3,
        ),
        _summary(
            mission_id="Mission_AcidTank",
            turn=4,
            total_turns=4,
            mission_kill_target=4,
            mission_kills_done=3,
            mission_kills_planned=0,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "kill_objective_failed"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True


def test_final_turn_kill_objective_allows_threshold():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_SnowStorm",
            turn=4,
            total_turns=4,
            mission_kill_target=5,
            mission_kills_done=4,
        ),
        _summary(
            mission_id="Mission_SnowStorm",
            turn=4,
            total_turns=4,
            mission_kill_target=5,
            mission_kills_done=5,
            mission_kills_planned=1,
        ),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_kill_limit_objective_blocks_over_cap_immediately():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Acid",
            turn=3,
            total_turns=4,
            mission_kill_limit=4,
            mission_kills_done=3,
        ),
        _summary(
            mission_id="Mission_Acid",
            turn=3,
            total_turns=4,
            mission_kill_limit=4,
            mission_kills_done=5,
            mission_kills_planned=2,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit, allow_dirty_plan=True) is True
    assert audit["violations"][0]["kind"] == "kill_limit_objective_failed"
    assert audit["violations"][0]["details"] == {
        "limit": 4,
        "planned_kills": 2,
    }
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_uncollected_pod_loss_blocks_plan():
    audit = audit_plan_safety(
        _summary(pods_present=1),
        _summary(pods_present=0, pods_collected=0),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert audit["violations"][0]["kind"] == "pod_lost"


def test_destroy_pod_allowance_only_covers_destroyed_pods():
    destroyed = audit_plan_safety(
        _summary(pods_present=1),
        _summary(pods_present=0, pods_collected=0),
    )
    unrecovered = audit_plan_safety(
        _summary(turn=4, total_turns=4, pods_present=1),
        _summary(turn=4, total_turns=4, pods_present=1, pods_collected=0),
    )

    assert plan_requires_safety_block(
        destroyed,
        allow_pod_destroy_dirty=True,
    ) is False
    assert plan_requires_safety_block(
        unrecovered,
        allow_pod_destroy_dirty=True,
    ) is True
    assert unrecovered["violations"][0]["kind"] == "pod_unrecovered_final"


def test_collected_pod_drop_is_clean():
    audit = audit_plan_safety(
        _summary(pods_present=1),
        _summary(pods_present=0, pods_collected=1),
    )

    assert audit["status"] == "CLEAN"
    assert plan_requires_safety_block(audit) is False


def test_final_turn_live_pod_blocks_until_recovered():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Satellite",
            turn=4,
            total_turns=4,
            pods_present=1,
        ),
        _summary(
            mission_id="Mission_Satellite",
            turn=4,
            total_turns=4,
            pods_present=1,
            pods_collected=0,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert plan_requires_safety_block(audit) is True
    assert plan_requires_safety_block(
        audit,
        allow_dirty_plan=True,
        allow_objective_loss_dirty=True,
    ) is False
    assert plan_requires_safety_block(
        audit,
        allow_pod_loss_dirty=True,
    ) is False
    assert audit["violations"][0]["kind"] == "pod_unrecovered_final"
    assert safety_loss_profile(audit)["label"] == "objective_loss"


def test_victory_in_one_live_pod_blocks_until_recovered():
    audit = audit_plan_safety(
        _summary(
            mission_id="Mission_Satellite",
            turn=3,
            total_turns=4,
            pods_present=1,
        ),
        _summary(
            mission_id="Mission_Satellite",
            turn=3,
            total_turns=4,
            pods_present=1,
            pods_collected=0,
        ),
    )

    assert audit["status"] == "DIRTY"
    assert audit["violations"][0]["kind"] == "pod_unrecovered_final"


def test_nonfinal_live_pod_can_remain_on_board():
    audit = audit_plan_safety(
        _summary(turn=2, total_turns=4, pods_present=1),
        _summary(turn=2, total_turns=4, pods_present=1, pods_collected=0),
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
