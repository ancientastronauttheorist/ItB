from src.solver.mission_unit_objectives import resolve_unit_objectives


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
