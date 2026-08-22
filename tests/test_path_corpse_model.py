from pathlib import Path

from src.model.board import Board
from src.model.pawn_stats import get_pawn_stats
from src.solver.verify import diff_states, snapshot_after_action
from src.loop import commands


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


SOURCE_CORPSE_TYPES = {
    "Dam_Pawn",
    "Train_Pawn",
    "Train_Damaged",
    "Train_Armored",
    "Train_Armored_Damaged",
    "Filler_Pawn",
    "SatelliteRocket",
    "ArchiveArtillery",
    "Pawn_Piston_U",
    "Pawn_Piston_R",
    "Pawn_Piston_D",
    "Pawn_Piston_L",
    "Pawn_Laser_U",
    "Pawn_Laser_R",
    "Pawn_Laser_D",
    "Pawn_Laser_L",
}


def test_modloader_exports_live_and_static_corpse_lifecycle() -> None:
    assert "pcall(function() return p:IsCorpse() end)" in MODLOADER
    assert "corpse = current_corpse" in MODLOADER
    assert "corpse_on_death = corpse_on_death" in MODLOADER
    assert "pawn_def and pawn_def.Corpse == true or false" in MODLOADER


def test_source_corpse_types_have_static_fallbacks() -> None:
    for pawn_type in SOURCE_CORPSE_TYPES:
        assert get_pawn_stats(pawn_type).corpse_on_death is True, pawn_type

    for pawn_type in ("Scorpion1", "ProtoBomb", "Freeze_Tank", "BigBomb"):
        assert get_pawn_stats(pawn_type).corpse_on_death is False, pawn_type


def test_board_distinguishes_persistent_and_transient_dead_pawns() -> None:
    board = Board.from_bridge_data({
        "units": [
            {
                "uid": 1,
                "type": "Dam_Pawn",
                "x": 1,
                "y": 1,
                "hp": 0,
                "max_hp": 2,
                "team": 2,
                "mech": False,
            },
            {
                "uid": 2,
                "type": "Scorpion1",
                "x": 2,
                "y": 1,
                "hp": 0,
                "max_hp": 2,
                "team": 6,
                "mech": False,
            },
            {
                "uid": 3,
                "type": "Scorpion1",
                "x": 3,
                "y": 1,
                "hp": 0,
                "max_hp": 2,
                "team": 6,
                "mech": False,
                "corpse": True,
            },
            {
                "uid": 4,
                "type": "PunchMech",
                "x": 4,
                "y": 1,
                "hp": 0,
                "max_hp": 3,
                "team": 1,
                "mech": True,
            },
            {
                "uid": 5,
                "type": "Dam_Pawn",
                "x": 5,
                "y": 1,
                "hp": 0,
                "max_hp": 2,
                "team": 2,
                "mech": False,
                "corpse_on_death": False,
            },
        ]
    })

    assert board.path_corpse_at(1, 1)
    assert not board.path_corpse_at(2, 1)
    assert board.path_corpse_at(3, 1)
    assert board.path_corpse_at(4, 1)
    assert not board.path_corpse_at(5, 1)
    assert board.wreck_at(2, 1), "combat corpse physics remains intentionally broad"


def test_verification_requires_persistent_corpse_but_allows_transient_removal() -> None:
    persistent = Board.from_bridge_data({
        "units": [{
            "uid": 1,
            "type": "ArchiveArtillery",
            "x": 3,
            "y": 3,
            "hp": 0,
            "max_hp": 2,
            "team": 1,
            "mech": False,
        }]
    })
    persistent_snapshot = snapshot_after_action(
        persistent, 0, mech_uid=99, events=[]
    )
    missing_persistent = diff_states(persistent_snapshot, Board())
    assert any(
        item["field"] == "missing_in_actual"
        for item in missing_persistent.unit_diffs
    )

    transient = Board.from_bridge_data({
        "units": [{
            "uid": 2,
            "type": "Scorpion1",
            "x": 4,
            "y": 3,
            "hp": 0,
            "max_hp": 2,
            "team": 6,
            "mech": False,
        }]
    })
    transient_snapshot = snapshot_after_action(
        transient, 0, mech_uid=99, events=[]
    )
    assert diff_states(transient_snapshot, Board()).is_empty()


def test_checkpoint_schema_accepts_source_corpse_only() -> None:
    tiles = [
        {"x": x, "y": y, "terrain": "ground"}
        for x in range(8)
        for y in range(8)
    ]

    def payload(unit: dict) -> dict:
        return {
            "tiles": tiles,
            "units": [unit],
            "attack_order": [],
            "grid_power": 7,
            "grid_power_max": 7,
            "turn": 1,
            "total_turns": 4,
            "remaining_spawns": 0,
            "mission_id": "Mission_Test",
            "mission_kill_target": 0,
            "mission_kill_limit": 0,
            "mission_kills_done": 0,
            "mission_mountain_target": 0,
            "mission_mountains_destroyed": 0,
            "repair_platform_target": 0,
            "repair_platforms_used": 0,
            "freeze_building_target": 0,
        }

    corpse = {
        "uid": 7,
        "type": "Pawn_Piston_U",
        "x": 3,
        "y": 3,
        "hp": 0,
        "max_hp": 1,
        "team": 2,
        "mech": False,
        "move": 0,
        "active": False,
        "corpse_on_death": True,
    }
    assert commands._held_end_turn_bridge_checkpoint_schema_error(
        payload(corpse)
    ) is None

    transient = dict(corpse, type="Scorpion1", corpse_on_death=False)
    assert commands._held_end_turn_bridge_checkpoint_schema_error(
        payload(transient)
    ) == "checkpoint_unit_hp_invalid"
