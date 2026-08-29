from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_position_observations_boundary import (
    ANALYSIS_KIND,
    DIR_NONE,
    INT_MAX,
    TEAM_ENEMY,
    TEAM_PLAYER,
    EnemyPositionObservationsBoundaryError,
    bridge_native_enemy_position_observations,
    build_enemy_position_observations_boundary,
    encode_enemy_position_observations_boundary,
    replay_board_is_dangerous,
    replay_board_is_dangerous_item,
    replay_board_is_pawn_team,
    replay_board_is_spawning,
    replay_distance_to_building,
    replay_distance_to_pawn,
    replay_pawn_is_avoiding_mines,
    replay_pawn_is_flying,
    replay_pawn_is_ranged,
    replay_score_team_match,
    validate_enemy_position_observations_boundary,
    validate_enemy_position_observations_boundary_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")
INVENTORY = (
    ROOT
    / "data"
    / "observatory"
    / "inventories"
    / "windows_build_13725832_31fe35265598_local_modified.json"
)
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_"
    "enemy_position_observations_boundary.json"
)


def _load(path: Path = BOUNDARY_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bridge_payload() -> dict:
    tiles = [
        {
            "x": x,
            "y": y,
            "dangerous_item": (x, y) == (1, 2),
        }
        for y in range(8)
        for x in range(8)
    ]
    return {
        "tiles": tiles,
        "units": [
            {"uid": 3, "ranged": 1, "avoiding_mines": False},
            {"uid": 4, "ranged": 0, "avoiding_mines": True},
            {
                "uid": 3,
                "ranged": 1,
                "avoiding_mines": False,
                "is_extra_tile": True,
            },
        ],
        "native_enemy_spawn_inputs": {
            "schema_version": 1,
            "current_snapshot_only": True,
            "dangerous_tiles_complete": True,
            "dangerous_tiles": [[0, 0], [6, 7]],
        },
        "native_enemy_position_inputs": {
            "schema_version": 1,
            "current_snapshot_only": True,
            "dangerous_item_tiles_complete": True,
            "dangerous_item_tiles": [[1, 2]],
            "pawn_flags_ordered_complete": True,
            "pawn_flags_ordered": [
                {"uid": 3, "ranged": True, "avoiding_mines": False},
                {"uid": 4, "ranged": False, "avoiding_mines": True},
            ],
        },
    }


def test_bridge_normalizer_closes_all_exact_current_native_position_carriers():
    assert bridge_native_enemy_position_observations(_bridge_payload()) == {
        "dangerous_points": frozenset({(0, 0), (6, 7)}),
        "dangerous_item_points": frozenset({(1, 2)}),
        "pawn_flags": {
            3: {"ranged": True, "avoiding_mines": False},
            4: {"ranged": False, "avoiding_mines": True},
        },
        "pawn_order": (3, 4),
        "complete_for_current_score_positioning": True,
        "current_snapshot_only": True,
        "future_candidate_time": False,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["native_enemy_position_inputs"].update(
            {"dangerous_item_tiles_complete": False}
        ),
        lambda data: data["tiles"][0].update({"dangerous_item": True}),
        lambda data: data["units"][0].update({"ranged": 0}),
        lambda data: data["native_enemy_position_inputs"][
            "pawn_flags_ordered"
        ].reverse(),
    ],
)
def test_bridge_normalizer_fails_closed_on_incomplete_or_disagreeing_carriers(
    mutate,
):
    data = _bridge_payload()
    mutate(data)
    with pytest.raises(EnemyPositionObservationsBoundaryError):
        bridge_native_enemy_position_observations(data)


def test_committed_map_binds_complete_native_observation_semantics():
    value = _load()
    result = validate_enemy_position_observations_boundary_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "f7871672fac450ff60196638bb35e28fb"
            "865f11844ce2cab76e9ba8bcafc8329"
        ),
        "native_score_positioning_observation_semantics_complete": True,
        "current_state_carrier_matrix_complete": True,
        "prospective_board_observations_complete": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 3,
        "source_file_count": 2,
        "method_binding_count": 17,
        "native_region_count": 22,
        "control_window_count": 4,
        "call_edge_count": 9,
        "carrier_count": 17,
        "replay_vector_count": 16,
        "finding_count": 10,
        "unresolved_count": 2,
        "native_score_positioning_observation_semantics_complete": True,
        "prospective_board_observations_complete": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_all_score_positioning_native_method_names_are_bound():
    bindings = {item["id"]: item for item in _load()["method_bindings"]}
    assert len(bindings) == 17
    assert bindings["board_is_dangerous"] == {
        "id": "board_is_dangerous",
        "owner": "Board",
        "name": "IsDangerous",
        "name_rva": "0x0043861c",
        "registration_rva": "0x00279d70",
        "registration_size": 34,
        "registration_sha256": (
            "eab17162c1ee63b83c63a9fb4c06c66"
            "f3035d213af78fc7f9f0ec97da08831e1"
        ),
        "member_target_rva": "0x001726a0",
        "implementation_rva": "0x001726a0",
    }
    assert bindings["board_is_pawn_team"]["member_target_rva"] == (
        "0x002e39d7"
    )
    assert bindings["board_is_pawn_team"]["implementation_rva"] == (
        "0x0016fc50"
    )
    assert bindings["board_is_pawn_team"]["this_adjustment"] == 12
    assert bindings["board_get_distance_to_pawn"][
        "dedicated_constructor_rva"
    ] == "0x00289230"


def test_dangerous_replay_uses_tile_flag_and_two_independent_point_vectors():
    assert replay_board_is_dangerous(
        [3, 3], tile_flag=True, first_points=[], second_points=[]
    )
    assert replay_board_is_dangerous(
        [3, 3], tile_flag=False, first_points=[[3, 3]], second_points=[]
    )
    assert replay_board_is_dangerous(
        [3, 3], tile_flag=False, first_points=[], second_points=[[3, 3]]
    )
    assert not replay_board_is_dangerous(
        [3, 3], tile_flag=False, first_points=[[3, 2]], second_points=[[2, 3]]
    )


def test_dangerous_item_exact_neutral_tuple_is_safe():
    assert not replay_board_is_dangerous_item(
        item_present=True,
        i_damage=0,
        i_push=DIR_NONE,
        i_shield=0,
        i_fire=0,
        i_smoke=0,
        s_pawn_present=False,
        i_acid=0,
        i_frozen=0,
    )
    assert not replay_board_is_dangerous_item(
        item_present=False,
        i_damage=9,
        i_push=0,
        i_shield=1,
        i_fire=1,
        i_smoke=1,
        s_pawn_present=True,
        i_acid=1,
        i_frozen=1,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("i_damage", 1),
        ("i_push", 0),
        ("i_shield", 1),
        ("i_fire", 1),
        ("i_smoke", 1),
        ("s_pawn_present", True),
        ("i_acid", 1),
        ("i_frozen", 1),
    ],
)
def test_each_dangerous_item_effect_is_independently_sufficient(field, value):
    payload = {
        "item_present": True,
        "i_damage": 0,
        "i_push": DIR_NONE,
        "i_shield": 0,
        "i_fire": 0,
        "i_smoke": 0,
        "s_pawn_present": False,
        "i_acid": 0,
        "i_frozen": 0,
    }
    payload[field] = value
    assert replay_board_is_dangerous_item(**payload)


def test_spawning_replay_uses_tile_flag_or_point_vector():
    assert replay_board_is_spawning(
        [2, 4], tile_flag=True, spawning_points=[]
    )
    assert replay_board_is_spawning(
        [2, 4], tile_flag=False, spawning_points=[[2, 4]]
    )
    assert not replay_board_is_spawning(
        [2, 4], tile_flag=False, spawning_points=[[4, 2]]
    )


def test_score_team_queries_match_native_one_and_six_semantics():
    assert replay_score_team_match(TEAM_PLAYER, TEAM_PLAYER)
    assert not replay_score_team_match(TEAM_ENEMY, TEAM_PLAYER)
    assert replay_score_team_match(TEAM_ENEMY, TEAM_ENEMY)
    assert replay_score_team_match(7, TEAM_ENEMY)
    assert not replay_score_team_match(5, TEAM_ENEMY)
    assert not replay_board_is_pawn_team(None, TEAM_PLAYER)
    assert replay_board_is_pawn_team(7, TEAM_ENEMY)


def test_distance_to_pawn_is_team_filtered_manhattan_and_empty_int_max():
    pawns = [
        {"point": [3, 2], "team": TEAM_PLAYER},
        {"point": [6, 5], "team": TEAM_ENEMY},
        {"point": [-1, -1], "team": TEAM_ENEMY},
        {"point": [0, 3], "team": 7},
    ]
    assert replay_distance_to_pawn([3, 3], pawns, TEAM_PLAYER) == 1
    assert replay_distance_to_pawn([3, 3], pawns, TEAM_ENEMY) == 3
    assert replay_distance_to_pawn([3, 3], [], TEAM_ENEMY) == INT_MAX


def test_distance_to_building_is_manhattan_and_empty_int_max():
    assert replay_distance_to_building([3, 3], [[0, 0], [5, 4]]) == 3
    assert replay_distance_to_building([3, 3], []) == INT_MAX


def test_pawn_definition_property_replays_preserve_native_types():
    assert replay_pawn_is_ranged(1)
    assert not replay_pawn_is_ranged(0)
    assert not replay_pawn_is_ranged(2)
    assert replay_pawn_is_avoiding_mines(True)
    assert replay_pawn_is_flying(
        definition_flying=False,
        runtime_flying=True,
        pawn_is_dead=False,
    )
    assert not replay_pawn_is_flying(
        definition_flying=True,
        runtime_flying=False,
        pawn_is_dead=True,
    )


@pytest.mark.parametrize(
    "operation",
    [
        lambda: replay_pawn_is_ranged(True),
        lambda: replay_pawn_is_avoiding_mines(1),
        lambda: replay_score_team_match(True, TEAM_PLAYER),
        lambda: replay_score_team_match(TEAM_PLAYER, 2),
        lambda: replay_distance_to_pawn(
            [3, 3], [{"point": [2, 2], "team": TEAM_ENEMY, "extra": 1}], TEAM_ENEMY
        ),
        lambda: replay_board_is_dangerous(
            [8, 0], tile_flag=False, first_points=[], second_points=[]
        ),
    ],
)
def test_replays_reject_type_scope_and_shape_drift(operation):
    with pytest.raises(EnemyPositionObservationsBoundaryError):
        operation()


def test_source_census_pins_only_stock_avoiding_mines_assignments():
    assert _load()["avoiding_mines_source_census"] == [
        {"path": "scripts/global.lua", "line": 153, "column": 2, "value": False},
        {"path": "scripts/pawns.lua", "line": 1288, "column": 3, "value": True},
        {"path": "scripts/pawns.lua", "line": 1304, "column": 3, "value": True},
    ]


def test_carrier_matrix_keeps_native_danger_separate_from_environment_danger():
    carriers = {
        item["observation"]: item for item in _load()["observation_carriers"]
    }
    assert carriers["Board:IsDangerous"] == {
        "observation": "Board:IsDangerous",
        "carrier": "native_enemy_spawn_inputs.dangerous_tiles",
        "status": "direct_exact_current",
        "source": "src/bridge/modloader.lua",
    }
    assert carriers["Board:IsDangerousItem"]["status"] == "direct_exact_current"
    assert carriers["Pawn:IsRanged"]["status"] == "direct_exact_current"
    assert carriers["Pawn:IsAvoidingMines"]["status"] == "direct_exact_current"

    bridge = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
        encoding="utf-8"
    )
    commands = (ROOT / "src" / "loop" / "commands.py").read_text(
        encoding="utf-8"
    )
    assert "Board:IsTargeted(Point(x, y))" in bridge
    assert "Board:IsSpawning(Point(x, y))" in bridge
    assert "Board:IsEnvironmentDanger" in bridge
    assert "return Board:IsDangerous(pt)" in bridge
    assert "return Board:IsDangerousItem(pt)" in bridge
    assert "native_enemy_spawn_inputs" in bridge
    assert "native_enemy_position_inputs" in bridge
    assert ":IsAvoidingMines()" in bridge
    assert ":IsRanged()" in bridge
    assert 'u.setdefault("ranged", stats.ranged)' in commands


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["native_regions"][8].update(
                {"sha256": "0" * 64}
            ),
            "fields differ",
        ),
        (
            lambda value: value["contracts"]["dangerous_item"]["safe_tuple"].update(
                {"iPush": 0}
            ),
            "fields differ",
        ),
        (
            lambda value: value["observation_carriers"][15].update(
                {"carrier": "environment_danger"}
            ),
            "fields differ",
        ),
        (
            lambda value: value["closure"].update(
                {"prospective_board_observations_complete": True}
            ),
            "fields differ",
        ),
    ],
)
def test_binding_rejects_native_contract_carrier_and_closure_drift(mutate, message):
    altered = copy.deepcopy(_load())
    mutate(altered)
    with pytest.raises(EnemyPositionObservationsBoundaryError, match=message):
        validate_enemy_position_observations_boundary_binding(altered)


def test_inventory_binding_and_encoding_fail_closed():
    inventory = _load(INVENTORY)
    altered = copy.deepcopy(inventory)
    altered["steam"]["build_id"] = "different"
    with pytest.raises(
        EnemyPositionObservationsBoundaryError,
        match="inventory fields differ",
    ):
        build_enemy_position_observations_boundary(CONTENT_ROOT, altered)

    value = _load()
    encoded = encode_enemy_position_observations_boundary(value)
    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_position_observations_boundary(value)


def test_exact_install_rebuilds_native_source_and_carrier_join_when_available():
    if not (CONTENT_ROOT / "Breach.exe").is_file():
        pytest.skip("exact local ITB installation is not available")

    result = validate_enemy_position_observations_boundary(
        CONTENT_ROOT,
        _load(INVENTORY),
        _load(),
    )
    assert result["status"] == "verified"
    assert result["native_score_positioning_observation_semantics_complete"] is True
    assert result["current_state_carrier_matrix_complete"] is True
    assert result["prospective_board_observations_complete"] is False
    assert result["simulator_change_required"] is False
