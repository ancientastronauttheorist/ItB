from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_score_positioning_semantics import (
    ANALYSIS_KIND,
    EnemyScorePositioningSemanticsError,
    build_enemy_score_positioning_semantics,
    encode_enemy_score_positioning_semantics,
    replay_enemy_score_positioning,
    replay_score_positioning_native_integer,
    validate_enemy_score_positioning_semantics,
    validate_enemy_score_positioning_semantics_binding,
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
SEMANTICS_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "callbacks"
    / "windows_build_13725832_31fe35265598_enemy_score_positioning_semantics.json"
)


def _load(path: Path = SEMANTICS_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _input(**overrides) -> dict:
    value = {
        "point": [3, 3],
        "board_is_pod": False,
        "terrain_is_hole": False,
        "pawn_is_flying": False,
        "board_is_targeted": False,
        "pawn_danger_score": None,
        "board_is_smoke": False,
        "board_is_fire": False,
        "pawn_is_fire": False,
        "board_is_spawning": False,
        "board_is_dangerous": False,
        "board_is_dangerous_item": False,
        "pawn_is_avoiding_mines": False,
        "terrain_is_water": False,
        "pawn_custom_position_score": 0,
        "pawn_team_is_player": False,
        "pawn_is_ranged": True,
        "adjacent_selected_enemy_pawn": None,
        "adjacent_building": None,
        "distance_to_selected_enemy_pawn": None,
        "distance_to_building": None,
    }
    value.update(overrides)
    return value


def _early(**overrides) -> dict:
    return _input(
        pawn_custom_position_score=None,
        pawn_team_is_player=None,
        pawn_is_ranged=None,
        **overrides,
    )


def _replay(**overrides) -> dict:
    return replay_enemy_score_positioning(**_input(**overrides))


def test_committed_map_binds_exact_source_projection_without_rounding_overclaim():
    value = _load()
    result = validate_enemy_score_positioning_semantics_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "462c5ee971ff5208174d29e3d60da655"
            "0d96325bfc1fb2a18511f3b03541dd62"
        ),
        "score_positioning_projection_complete": True,
        "native_integer_conversion_parametric_complete": True,
        "x87_rounding_mode_observed": False,
        "native_pawn_score_helpers_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 6,
        "source_region_count": 1,
        "native_region_count": 3,
        "replay_vector_count": 14,
        "finding_count": 9,
        "unresolved_count": 4,
        "score_positioning_projection_complete": True,
        "native_integer_conversion_parametric_complete": True,
        "x87_rounding_mode_observed": False,
        "native_pawn_score_helpers_complete": True,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_exact_source_and_native_conversion_regions_are_pinned():
    value = _load()
    source = value["source_regions"][0]
    native = {item["id"]: item for item in value["native_regions"]}

    assert source == {
        "id": "score_positioning",
        "source_path": "scripts/global.lua",
        "symbol": "ScorePositioning",
        "line": 446,
        "body_size": 2075,
        "body_sha256": (
            "320210ee36aaf90a77e661e33e5c162b"
            "d9734066479f5b4052ec23276f9dfff5"
        ),
    }
    assert native["score_positioning_wrapper"]["start_rva"] == "0x000f7870"
    assert native["named_integer_invoker"]["start_rva"] == "0x000f8770"
    assert native["lua_tointeger"]["start_rva"] == "0x000016d0"
    assert native["lua_tointeger"]["size"] == 125
    assert native["lua_tointeger"]["conversion_instruction_hex"] == (
        "dd45f0db5de4"
    )
    assert native["lua_tointeger"]["conversion_instructions"] == [
        "fld qword ptr [ebp-0x10]",
        "fistp dword ptr [ebp-0x1c]",
    ]


def test_native_pawn_helper_dependency_closes_stock_defaults_without_overclaim():
    value = _load()
    dependency = next(
        item
        for item in value["dependencies"]
        if item["id"] == "enemy_position_score_helpers_boundary"
    )
    assert dependency["file_sha256"] == (
        "989c2d74194b810e14ae8327b17cbaa9"
        "535a8ec83acedefad951bc9ad77c8ff9"
    )
    assert dependency["canonical_sha256"] == (
        "9f572158d5e8dc760974166a4ad6a21f"
        "68a68324d0ec6d97eb6f8d02d4fa3cd9"
    )
    assert value["contracts"]["unmodified_shipped_danger_score"] == -10
    assert value["contracts"]["unmodified_shipped_custom_position_score"] == 0
    assert value["contracts"][
        "stock_helper_defaults_require_runtime_rounding_mode"
    ] is False
    assert value["closure"]["native_pawn_score_helpers_complete"] is True
    assert value["closure"][
        "unmodified_shipped_pawn_score_defaults_complete"
    ] is True
    assert value["unresolved"][1]["id"] == (
        "runtime_or_modded_pawn_score_mutation"
    )


def test_hazard_precedence_starts_with_pod_hole_and_targeted_danger():
    pod = replay_enemy_score_positioning(
        **_early(
            board_is_pod=True,
            terrain_is_hole=True,
            board_is_targeted=True,
        )
    )
    hole = replay_enemy_score_positioning(
        **_early(terrain_is_hole=True, board_is_targeted=True)
    )
    targeted = replay_enemy_score_positioning(
        **_early(board_is_targeted=True, pawn_danger_score=-7)
    )

    assert (pod["selected_branch"], pod["lua_result"]) == ("pod", -100)
    assert (hole["selected_branch"], hole["lua_result"]) == (
        "grounded_hole",
        -10,
    )
    assert (targeted["selected_branch"], targeted["lua_result"]) == (
        "targeted_danger_score",
        -7,
    )


def test_flying_hole_continues_but_targeted_still_precedes_smoke():
    result = replay_enemy_score_positioning(
        **_early(
            terrain_is_hole=True,
            pawn_is_flying=True,
            board_is_targeted=True,
            pawn_danger_score=9,
            board_is_smoke=True,
        )
    )
    assert result["selected_branch"] == "targeted_danger_score"
    assert result["lua_result"] == 9


@pytest.mark.parametrize(
    ("overrides", "branch", "score"),
    [
        ({"board_is_smoke": True, "board_is_fire": True}, "smoke", -2),
        ({"board_is_fire": True}, "new_fire", -10),
        ({"board_is_spawning": True}, "spawning", -10),
        ({"board_is_dangerous": True}, "dangerous", -10),
        (
            {
                "board_is_dangerous_item": True,
                "pawn_is_avoiding_mines": True,
            },
            "dangerous_item_avoided",
            -10,
        ),
        ({"terrain_is_water": True}, "grounded_water", -5),
    ],
)
def test_remaining_hazard_order_and_scores(overrides, branch, score):
    result = replay_enemy_score_positioning(**_early(**overrides))
    assert result["selected_branch"] == branch
    assert result["lua_result"] == score


def test_fire_immunity_flight_and_mine_nonavoidance_fall_through():
    result = _replay(
        board_is_fire=True,
        pawn_is_fire=True,
        board_is_dangerous_item=True,
        pawn_is_avoiding_mines=False,
        terrain_is_water=True,
        pawn_is_flying=True,
    )
    assert result["selected_branch"] == "ranged_interior"
    assert result["lua_result"] == 5


def test_custom_score_precedes_hardcoded_stock_corner_and_edge():
    custom = replay_enemy_score_positioning(
        **_input(
            point=[0, 0],
            pawn_custom_position_score=8,
            pawn_team_is_player=None,
            pawn_is_ranged=None,
        )
    )
    corner = replay_enemy_score_positioning(
        **_input(point=[0, 7], pawn_team_is_player=None, pawn_is_ranged=None)
    )
    edge = replay_enemy_score_positioning(
        **_input(point=[3, 7], pawn_team_is_player=None, pawn_is_ranged=None)
    )
    outside = _replay(point=[8, 3])

    assert (custom["selected_branch"], custom["lua_result"]) == (
        "custom_nonzero",
        8,
    )
    assert (corner["selected_branch"], corner["lua_result"]) == (
        "stock_corner",
        -2,
    )
    assert (edge["selected_branch"], edge["lua_result"]) == ("stock_edge", 0)
    assert outside["selected_branch"] == "ranged_interior"


@pytest.mark.parametrize(
    ("pawn_team_is_player", "selected"),
    [(True, "TEAM_ENEMY"), (False, "TEAM_PLAYER")],
)
def test_binary_enemy_team_selection_matches_source_caveat(
    pawn_team_is_player,
    selected,
):
    result = _replay(pawn_team_is_player=pawn_team_is_player)
    assert result["selected_enemy_team"] == selected


def test_melee_checks_each_direction_pawn_before_building_and_short_circuits():
    pawn = _replay(
        pawn_is_ranged=False,
        adjacent_selected_enemy_pawn=[False, True, False, False],
        adjacent_building=[False, True, False, False],
    )
    building = _replay(
        pawn_is_ranged=False,
        adjacent_selected_enemy_pawn=[False, False, False, False],
        adjacent_building=[False, False, True, False],
    )

    assert pawn["selected_branch"] == "melee_adjacent_enemy_pawn"
    assert pawn["lua_result"] == 5
    assert not any(
        step.get("call") == "Board:IsBuilding"
        and step.get("direction_offset") == 1
        for step in pawn["trace"]
    )
    assert building["selected_branch"] == "melee_adjacent_building"
    assert building["lua_result"] == 5


@pytest.mark.parametrize(
    ("closest", "numerator", "denominator", "value"),
    [(0, 5, 1, 5), (1, 9, 2, 4.5), (3, 7, 2, 3.5), (10, 0, 1, 0), (99, 0, 1, 0)],
)
def test_melee_distance_formula_preserves_exact_half_points(
    closest,
    numerator,
    denominator,
    value,
):
    result = _replay(
        pawn_is_ranged=False,
        adjacent_selected_enemy_pawn=[False] * 4,
        adjacent_building=[False] * 4,
        distance_to_selected_enemy_pawn=closest,
        distance_to_building=99,
    )
    assert result["selected_branch"] == "melee_distance"
    assert result["lua_result_exact"] == {
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
    }
    assert result["lua_result"] == value


def test_x87_integer_conversion_replay_distinguishes_all_rounding_modes():
    positive = {
        mode: replay_score_positioning_native_integer(
            numerator=7,
            denominator=2,
            x87_rounding_mode=mode,
        )["result"]
        for mode in ("nearest_even", "down", "up", "toward_zero")
    }
    negative = {
        mode: replay_score_positioning_native_integer(
            numerator=-7,
            denominator=2,
            x87_rounding_mode=mode,
        )["result"]
        for mode in ("nearest_even", "down", "up", "toward_zero")
    }

    assert positive == {
        "nearest_even": 4,
        "down": 3,
        "up": 4,
        "toward_zero": 3,
    }
    assert negative == {
        "nearest_even": -4,
        "down": -4,
        "up": -3,
        "toward_zero": -3,
    }


def test_nearest_even_ties_use_even_integer_not_always_away_from_zero():
    assert replay_score_positioning_native_integer(
        numerator=5,
        denominator=2,
        x87_rounding_mode="nearest_even",
    )["result"] == 2
    assert replay_score_positioning_native_integer(
        numerator=3,
        denominator=2,
        x87_rounding_mode="nearest_even",
    )["result"] == 2


def test_optional_inputs_fail_closed_when_source_would_not_or_did_call_them():
    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="danger_score presence",
    ):
        replay_enemy_score_positioning(
            **_early(board_is_targeted=True, pawn_danger_score=None)
        )

    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="custom_position_score presence",
    ):
        _replay(pawn_custom_position_score=None)

    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="interior positioning requires",
    ):
        _replay(pawn_team_is_player=None)

    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="four ordered adjacency",
    ):
        _replay(pawn_is_ranged=False)

    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="both distance observations",
    ):
        _replay(
            pawn_is_ranged=False,
            adjacent_selected_enemy_pawn=[False] * 4,
            adjacent_building=[False] * 4,
        )


def test_replay_rejects_bad_types_lengths_distances_and_rounding_mode():
    with pytest.raises(EnemyScorePositioningSemanticsError, match="point"):
        _replay(point=[1, 2, 3])
    with pytest.raises(EnemyScorePositioningSemanticsError, match="Boolean"):
        _replay(board_is_pod=1)
    with pytest.raises(EnemyScorePositioningSemanticsError, match="four-entry"):
        _replay(
            pawn_is_ranged=False,
            adjacent_selected_enemy_pawn=[False] * 3,
            adjacent_building=[False] * 4,
        )
    with pytest.raises(EnemyScorePositioningSemanticsError, match="nonnegative"):
        _replay(
            pawn_is_ranged=False,
            adjacent_selected_enemy_pawn=[False] * 4,
            adjacent_building=[False] * 4,
            distance_to_selected_enemy_pawn=-1,
            distance_to_building=5,
        )
    with pytest.raises(EnemyScorePositioningSemanticsError, match="x87_rounding"):
        replay_score_positioning_native_integer(
            numerator=7,
            denominator=2,
            x87_rounding_mode="unknown",
        )


def test_committed_replay_vectors_recompute_from_public_helper():
    for vector in _load()["replay_vectors"]:
        assert replay_enemy_score_positioning(**vector["input"]) == vector["expected"]


def test_binding_rejects_source_native_rounding_and_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["source_regions"][0]["body_sha256"] = "0" * 64
    with pytest.raises(EnemyScorePositioningSemanticsError, match="fields differ"):
        validate_enemy_score_positioning_semantics_binding(altered)

    altered = copy.deepcopy(value)
    altered["native_regions"][2]["conversion_instruction_hex"] = "90"
    with pytest.raises(EnemyScorePositioningSemanticsError, match="fields differ"):
        validate_enemy_score_positioning_semantics_binding(altered)

    altered = copy.deepcopy(value)
    altered["closure"]["x87_rounding_mode_observed"] = True
    with pytest.raises(EnemyScorePositioningSemanticsError, match="fields differ"):
        validate_enemy_score_positioning_semantics_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][-1]["expected"]["lua_result"] = 3
    with pytest.raises(EnemyScorePositioningSemanticsError, match="fields differ"):
        validate_enemy_score_positioning_semantics_binding(altered)


def test_inventory_binding_and_encoding_fail_closed():
    inventory = _load(INVENTORY)
    altered = copy.deepcopy(inventory)
    altered["steam"]["build_id"] = "different"
    with pytest.raises(
        EnemyScorePositioningSemanticsError,
        match="inventory fields differ",
    ):
        build_enemy_score_positioning_semantics(CONTENT_ROOT, altered)

    value = _load()
    encoded = encode_enemy_score_positioning_semantics(value)
    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_score_positioning_semantics(value)


def test_exact_install_rebuilds_source_executable_and_lua_dll_join_when_available():
    if not (CONTENT_ROOT / "Breach.exe").is_file():
        pytest.skip("exact local ITB installation is not available")

    result = validate_enemy_score_positioning_semantics(
        CONTENT_ROOT,
        _load(INVENTORY),
        _load(),
    )
    assert result["status"] == "verified"
    assert result["score_positioning_projection_complete"] is True
    assert result["native_integer_conversion_parametric_complete"] is True
    assert result["x87_rounding_mode_observed"] is False
    assert result["native_pawn_score_helpers_complete"] is True
    assert result["simulator_change_required"] is False
