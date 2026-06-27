from src.solver.mission_unit_objectives import (
    inject_into_bridge,
    resolve_unit_objectives,
)


def test_mission_tanks_protects_archive_tanks():
    resolved = resolve_unit_objectives("Mission_Tanks")

    assert resolved["destroy"] == []
    assert "Archive_Tank" in resolved["protect"]


def test_mission_acidstorm_destroys_storm_generator():
    resolved = resolve_unit_objectives("Mission_AcidStorm")

    assert "Storm_Generator" in resolved["destroy"]
    assert resolved["protect"] == []


def test_mission_dam_destroys_dam_pawn():
    resolved = resolve_unit_objectives("Mission_Dam")

    assert "Dam_Pawn" in resolved["destroy"]
    assert resolved["protect"] == []


def test_bonus_debris_injects_bonus_debris_destroy_objective():
    bridge_data = {
        "mission_id": "Mission_Survive",
        "bonus_objective_ids": [7],
        "units": [
            {"uid": 1, "type": "BonusDebris", "hp": 1},
            {"uid": 2, "type": "Hornet1", "hp": 2},
        ],
    }

    resolved = inject_into_bridge(bridge_data)

    assert resolved["destroy"] == ["BonusDebris"]
    assert bridge_data["destroy_objective_unit_types"] == ["BonusDebris"]


def test_bonus_debris_id_without_bonus_debris_unit_is_noop():
    bridge_data = {
        "mission_id": "Mission_Survive",
        "bonus_objective_ids": [7],
        "units": [{"uid": 2, "type": "Hornet1", "hp": 2}],
    }

    resolved = inject_into_bridge(bridge_data)

    assert resolved["destroy"] == []
    assert bridge_data["destroy_objective_unit_types"] == []


def test_ae_boss_missions_mark_leaders_as_destroy_objectives():
    expected = {
        "Mission_BlobberBoss": "BlobberBoss",
        "Mission_BouncerBoss": "BouncerBoss",
        "Mission_BurnbugBoss": "BurnbugBoss",
        "Mission_CrabBoss": "CrabBoss",
        "Mission_DungBoss": "DungBoss",
        "Mission_MosquitoBoss": "MosquitoBoss",
        "Mission_ScarabBoss": "ScarabBoss",
        "Mission_ShamanBoss": "ShamanBoss",
        "Mission_StarfishBoss": "StarfishBoss",
    }

    for mission_id, leader_type in expected.items():
        resolved = resolve_unit_objectives(mission_id)
        assert leader_type in resolved["destroy"]
        assert resolved["protect"] == []
