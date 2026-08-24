from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_target_area_callback_boundary import (
    ANALYSIS_KIND,
    MAX_REPLAY_POINTS,
    REPLAY_KIND,
    EnemyTargetAreaCallbackBoundaryError,
    encode_enemy_target_area_callback_boundary_map,
    replay_enemy_target_area_callback,
    validate_enemy_target_area_callback_boundary_map,
    validate_enemy_target_area_callback_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_"
    "enemy_target_area_callback_boundary.json"
)
EXECUTABLE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def _replay(**overrides: object) -> dict:
    payload = {
        "board_width": 8,
        "board_height": 8,
        "origin": [3, 4],
        "cached_points": [[7, 7], [1, 1]],
        "two_click": False,
        "second_target": [-1, -1],
        "get_target_area_points": [[3, 3]],
        "get_second_target_area_points": None,
    }
    payload.update(overrides)
    return replay_enemy_target_area_callback(**payload)


def test_committed_map_binds_complete_wrapper_without_lua_overclaim():
    value = _load()
    result = validate_enemy_target_area_callback_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "bcac4ea3c6a6e5cec73d95ea27f0edab5ef592de09d135200ea5efb8b66c405f"
        ),
        "parameterized_native_wrapper_complete": True,
        "invalid_origin_clears_cache": True,
        "lua_callback_point_construction_complete": False,
        "skill_effect_materialization_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 2,
        "region_count": 9,
        "control_window_count": 15,
        "direct_edge_count": 13,
        "jump_edge_count": 1,
        "call_inventory_count": 2,
        "data_anchor_count": 4,
        "instruction_anchor_count": 1,
        "replay_vector_count": 12,
        "finding_count": 6,
        "unresolved_count": 4,
        "parameterized_native_wrapper_complete": True,
        "invalid_origin_clears_cache": True,
        "lua_callback_point_construction_complete": False,
        "skill_effect_materialization_complete": False,
        "complete_enemy_phase_forecast": False,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_board_context_chain_names_exact_adjustment_slot_and_target():
    value = _load()
    windows = {item["id"]: item for item in value["control_windows"]}
    pointers = {item["id"]: item for item in value["data_anchors"]}
    jumps = {item["id"]: item for item in value["jump_edges"]}

    assert "Board +0x0c" in windows["addpawn_passes_board_secondary_context"]["meaning"]
    assert "Skill +0x110" in windows["skill_ctor_context_and_empty_cache"]["meaning"]
    assert pointers["board_secondary_isvalid_slot"]["data_rva"] == "0x0042e26c"
    assert pointers["board_secondary_isvalid_slot"]["data_hex"] == "c0a95700"
    assert jumps["secondary_thunk_to_board_isvalid"]["from_rva"] == "0x0017a9c3"
    assert jumps["secondary_thunk_to_board_isvalid"]["target_rva"] == "0x00162280"


def test_complete_direct_call_inventories_are_exact():
    inventories = {item["id"]: item for item in _load()["call_inventories"]}

    target_sites = inventories["target_area_callback_callers"]
    assert target_sites["complete_direct_call_count"] == 6
    assert [site["call_rva"] for site in target_sites["sites"]] == [
        "0x0022792d",
        "0x00228663",
        "0x00229293",
        "0x00268971",
        "0x00269884",
        "0x0026a0cc",
    ]
    context_sites = inventories["skill_context_writer_callers"]
    assert context_sites["complete_direct_call_count"] == 6
    assert next(
        item for item in context_sites["sites"] if item["reviewed_role"] == "Board:AddPawn"
    )["call_rva"] == "0x0016e916"


@pytest.mark.parametrize("origin", [[-1, 4], [3, -1], [8, 7], [7, 8]])
def test_invalid_origin_clears_nonempty_cache_and_invokes_no_callback(origin):
    result = _replay(origin=origin, get_target_area_points=None)

    assert result["replay_kind"] == REPLAY_KIND
    assert result["origin_valid"] is False
    assert result["selected_callback"] is None
    assert result["callback_arguments"] == []
    assert result["callback_points_consumed"] is None
    assert result["cache_before"] == [[7, 7], [1, 1]]
    assert result["cache_after"] == []
    assert result["returned_points"] == []


def test_regular_callback_filter_is_negative_only_and_stable():
    callback_points = [
        [2, 2],
        [-1, 2],
        [2, 2],
        [9, 12],
        [3, -1],
        [0, 0],
    ]
    result = _replay(get_target_area_points=callback_points)

    assert result["origin_valid"] is True
    assert result["selected_callback"] == "GetTargetArea"
    assert result["callback_arguments"] == [[3, 4]]
    assert result["callback_points_consumed"] == callback_points
    assert result["removed_negative_points"] == [[-1, 2], [3, -1]]
    assert result["cache_after"] == [[2, 2], [2, 2], [9, 12], [0, 0]]
    assert result["returned_points"] == result["cache_after"]


def test_two_click_dispatches_second_callback_with_two_point_arguments():
    result = _replay(
        two_click=True,
        second_target=[5, 6],
        get_target_area_points=None,
        get_second_target_area_points=[[5, 6], [4, 4]],
    )

    assert result["selected_callback"] == "GetSecondTargetArea"
    assert result["callback_arguments"] == [[3, 4], [5, 6]]
    assert result["returned_points"] == [[5, 6], [4, 4]]


@pytest.mark.parametrize("second_target", [[-1, 6], [5, -1]])
def test_either_minus_one_second_coordinate_falls_back_to_regular(second_target):
    result = _replay(two_click=True, second_target=second_target)

    assert result["selected_callback"] == "GetTargetArea"
    assert result["callback_arguments"] == [[3, 4]]


def test_negative_non_sentinel_second_coordinates_still_select_second_callback():
    result = _replay(
        two_click=True,
        second_target=[-2, -3],
        get_target_area_points=None,
        get_second_target_area_points=[[-2, -3], [4, 5]],
    )

    assert result["selected_callback"] == "GetSecondTargetArea"
    assert result["callback_arguments"] == [[3, 4], [-2, -3]]
    assert result["removed_negative_points"] == [[-2, -3]]
    assert result["returned_points"] == [[4, 5]]


@pytest.mark.parametrize("origin", [[0, 0], [7, 7]])
def test_board_boundary_corners_are_valid(origin):
    assert _replay(origin=origin)["origin_valid"] is True


def test_selected_callback_input_schema_rejects_fabricated_unused_outputs():
    with pytest.raises(
        EnemyTargetAreaCallbackBoundaryError,
        match="invalid-origin replay must not supply callback output",
    ):
        _replay(origin=[-1, 0])
    with pytest.raises(
        EnemyTargetAreaCallbackBoundaryError,
        match="requires only its selected callback output",
    ):
        _replay(
            get_target_area_points=[[1, 1]],
            get_second_target_area_points=[[2, 2]],
        )
    with pytest.raises(
        EnemyTargetAreaCallbackBoundaryError,
        match="GetSecondTargetArea",
    ):
        _replay(two_click=True, second_target=[2, 2])


def test_input_types_signed_domains_and_tooling_limit_fail_closed():
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="board_width"):
        _replay(board_width=0)
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="boolean"):
        _replay(two_click=1)
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="signed 32-bit"):
        _replay(origin=[1 << 40, 0])
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="two-integer"):
        _replay(origin=[0])
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="tooling limit"):
        _replay(cached_points=[[0, 0]] * (MAX_REPLAY_POINTS + 1))


def test_every_committed_replay_vector_recomputes_exactly():
    for vector in _load()["replay_vectors"]:
        assert replay_enemy_target_area_callback(**vector["input"]) == vector["expected"]


def test_binding_rejects_control_flow_pointer_and_replay_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["control_windows"][1]["meaning"] = "reuse the cache"
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="fields differ"):
        validate_enemy_target_area_callback_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["data_anchors"][0]["data_hex"] = "c8a95700"
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="fields differ"):
        validate_enemy_target_area_callback_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["replay_vectors"][0]["expected"]["cache_after"] = [[7, 7]]
    with pytest.raises(EnemyTargetAreaCallbackBoundaryError, match="fields differ"):
        validate_enemy_target_area_callback_boundary_map_binding(altered)


def test_encoding_is_deterministic_and_round_trips():
    value = _load()
    encoded = encode_enemy_target_area_callback_boundary_map(value)

    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_target_area_callback_boundary_map(value)


def test_exact_installed_executable_rebuilds_committed_map_when_available():
    if not EXECUTABLE.is_file():
        pytest.skip("exact local ITB executable is not available")

    result = validate_enemy_target_area_callback_boundary_map(EXECUTABLE, _load())
    assert result["status"] == "verified"
    assert result["parameterized_native_wrapper_complete"] is True
    assert result["invalid_origin_clears_cache"] is True
    assert result["lua_callback_point_construction_complete"] is False
    assert result["skill_effect_materialization_complete"] is False
    assert result["simulator_change_required"] is False
