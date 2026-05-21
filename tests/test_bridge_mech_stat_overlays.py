from src.bridge import reader
from src.model.board import Board


SAVE_SNIPPET = """
["pawn1"] = {["type"] = "JetMech", ["id"] = 0, ["mech"] = true,
["healthPower"] = {0, },
["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Michael Lee", ["name_id"] = "", ["skill1"] = 0, ["skill2"] = 2, ["level"] = 2, },
["health"] = 2, ["max_health"] = 4, }


["pawn2"] = {["type"] = "PulseMech", ["id"] = 2, ["mech"] = true,
["healthPower"] = {1, },
["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Cinnabar", ["name_id"] = "", ["skill1"] = 10, ["skill2"] = 1, ["level"] = 2, },
["bInfected"] = true, ["health"] = 4, ["max_health"] = 5, }


["pawn3"] = {["type"] = "Scorpion2", ["id"] = 700, ["mech"] = false,
["health"] = 5, ["max_health"] = 5, }
"""


def test_parse_mech_stat_overlays_reads_effective_max_hp_and_pilot_fields():
    records = reader._parse_mech_stat_overlays_from_save_text(SAVE_SNIPPET)

    assert set(records) == {0, 2}
    assert records[0]["type"] == "JetMech"
    assert records[0]["max_hp"] == 4
    assert records[0]["pilot_name"] == "Michael Lee"
    assert records[0]["pilot_id"] == "Pilot_Archive"
    assert records[0]["pilot_skill2"] == 2
    assert records[0]["pilot_level"] == 2
    assert records[2]["type"] == "PulseMech"
    assert records[2]["max_hp"] == 5
    assert records[2]["health_power"] == 1
    assert records[2]["infected"] is True


def test_read_mech_stat_overlays_falls_back_to_undo_save(
    monkeypatch, tmp_path
):
    profile_dir = tmp_path / "profile_Alpha"
    profile_dir.mkdir()
    (profile_dir / "undoSave.lua").write_text(SAVE_SNIPPET)
    monkeypatch.setattr(
        reader.os.path,
        "expanduser",
        lambda path: str(profile_dir)
        if path.endswith("profile_Alpha")
        else path,
    )

    records = reader._read_mech_stat_overlays_from_save()

    assert records[0]["type"] == "JetMech"
    assert records[0]["max_hp"] == 4


def test_apply_save_mech_stat_overlays_patches_max_hp_without_touching_live_hp(
    monkeypatch,
):
    monkeypatch.setattr(
        reader,
        "_read_mech_stat_overlays_from_save",
        lambda: reader._parse_mech_stat_overlays_from_save_text(SAVE_SNIPPET),
    )
    bridge_data = {
        "grid_power": 4,
        "grid_power_max": 7,
        "units": [
            {
                "uid": 0,
                "type": "JetMech",
                "x": 3,
                "y": 5,
                "hp": 3,
                "max_hp": 2,
                "team": 1,
                "mech": True,
                "move": 4,
                "active": False,
                "weapons": ["Brute_Jetmech"],
                "pilot_skills": ["skill2=2"],
            },
            {
                "uid": 2,
                "type": "PulseMech",
                "x": 2,
                "y": 2,
                "hp": 4,
                "max_hp": 3,
                "team": 1,
                "mech": True,
                "move": 4,
                "active": True,
                "weapons": ["Science_Repulse"],
            },
        ],
    }

    updates = reader._apply_save_mech_stat_overlays(bridge_data)

    assert [u["uid"] for u in updates] == [0, 2]
    jet = bridge_data["units"][0]
    pulse = bridge_data["units"][1]
    assert jet["hp"] == 3
    assert jet["max_hp"] == 4
    assert jet["bridge_reported_max_hp"] == 2
    assert jet["pilot_name"] == "Michael Lee"
    assert jet["pilot_skills"] == ["skill2=2"]
    assert pulse["hp"] == 4
    assert pulse["max_hp"] == 5
    assert pulse["infected"] is True
    assert pulse["pilot_skills"] == ["skill1=10", "skill2=1"]
    assert bridge_data["mech_stat_overlays"][0]["pos"] == "C5"
    assert bridge_data["pilot_calibration_requests"][0]["capture_hint"]

    board = Board.from_bridge_data(bridge_data)
    units = {unit.uid: unit for unit in board.units}
    assert units[0].hp == 3
    assert units[0].max_hp == 4
    assert units[2].hp == 4
    assert units[2].max_hp == 5
    assert units[2].infected is True


def test_apply_save_mech_stat_overlays_ignores_uid_type_mismatch(monkeypatch):
    monkeypatch.setattr(
        reader,
        "_read_mech_stat_overlays_from_save",
        lambda: {0: {"type": "JetMech", "max_hp": 4}},
    )
    bridge_data = {
        "units": [
            {
                "uid": 0,
                "type": "RocketMech",
                "hp": 3,
                "max_hp": 3,
                "team": 1,
                "mech": True,
            },
        ],
    }

    assert reader._apply_save_mech_stat_overlays(bridge_data) == []
    assert bridge_data["units"][0]["max_hp"] == 3
    assert "mech_stat_overlays" not in bridge_data
