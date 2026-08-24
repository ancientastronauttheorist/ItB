from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.enemy_position_score_helpers_boundary import (
    ANALYSIS_KIND,
    EnemyPositionScoreHelpersBoundaryError,
    build_enemy_position_score_helpers_boundary,
    encode_enemy_position_score_helpers_boundary,
    replay_stock_enemy_position_score_helpers,
    validate_enemy_position_score_helpers_boundary,
    validate_enemy_position_score_helpers_boundary_binding,
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
    "enemy_position_score_helpers_boundary.json"
)


def _load(path: Path = BOUNDARY_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_map_binds_complete_stock_helper_results():
    value = _load()
    result = validate_enemy_position_score_helpers_boundary_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "9f572158d5e8dc760974166a4ad6a21f"
            "68a68324d0ec6d97eb6f8d02d4fa3cd9"
        ),
        "native_helper_call_paths_complete": True,
        "shipped_source_default_census_complete": True,
        "unmodified_shipped_results_complete": True,
        "simulator_change_required": False,
        "simulator_version": 408,
    }
    assert value["summary"] == {
        "dependency_count": 1,
        "source_region_count": 2,
        "scanned_shipped_lua_file_count": 152,
        "native_region_count": 12,
        "native_string_count": 6,
        "call_edge_count": 6,
        "replay_vector_count": 1,
        "finding_count": 6,
        "unresolved_count": 1,
        "unmodified_shipped_results_complete": True,
        "simulator_change_required": False,
        "simulator_version": 408,
    }


def test_exact_source_regions_pin_getter_generator_and_pawn_defaults():
    source = {item["id"]: item for item in _load()["source_regions"]}
    assert source["create_class"] == {
        "id": "create_class",
        "source_path": "scripts/global.lua",
        "symbol": "CreateClass",
        "line": 86,
        "body_size": 430,
        "body_sha256": (
            "214fce796c535562d79f4cdeef89be1e"
            "098b7652b2444c6957702b6a6aed29f9"
        ),
    }
    assert source["pawn_defaults_and_getter_install"]["line"] == 107
    assert source["pawn_defaults_and_getter_install"]["body_size"] == 1330
    assert source["pawn_defaults_and_getter_install"]["body_sha256"] == (
        "8f38b9c9ec4bb4acc43da66118ff1399"
        "f2ec43e342336155b332bf8c94e68ff9"
    )


def test_complete_active_source_census_has_defaults_and_no_explicit_getters():
    census = _load()["source_census"]
    assert census["scanned_inventory_script_file_count"] == 305
    assert census["scanned_shipped_lua_file_count"] == 152
    assert census["excluded_local_loader"] == "scripts/modloader.lua"
    assert census["active_occurrences"] == {
        "ScoreDanger": [
            {"path": "scripts/global.lua", "line": 141, "column": 2}
        ],
        "PositionScore": [
            {"path": "scripts/global.lua", "line": 149, "column": 2}
        ],
        "GetScoreDanger": [],
        "GetPositionScore": [],
        "GetCustomPositionScore": [
            {"path": "scripts/global.lua", "line": 475, "column": 22}
        ],
    }
    assert census["explicit_override_count"] == 0


def test_registration_windows_bind_unique_member_pointers_and_names():
    value = _load()
    regions = {item["id"]: item for item in value["native_regions"]}
    strings = {item["id"]: item for item in value["native_strings"]}
    pointers = {
        item["id"]: item for item in value["unique_member_pointers"]
    }

    assert regions["get_danger_score_registration"]["start_rva"] == (
        "0x0027c040"
    )
    assert regions["pawn_get_danger_score"]["start_rva"] == "0x002397f0"
    assert regions["pawn_get_danger_score"]["size"] == 57
    assert regions["pawn_get_custom_position_score"]["start_rva"] == (
        "0x0023c5f0"
    )
    assert regions["pawn_get_custom_position_score"]["size"] == 147
    assert pointers["get_danger_score_member_pointer"]["target_va"] == (
        "0x006397f0"
    )
    assert pointers["get_custom_position_score_member_pointer"][
        "target_va"
    ] == "0x0063c5f0"
    assert strings["score_danger_field"]["value"] == "ScoreDanger"
    assert strings["get_position_score_method"]["value"] == (
        "GetPositionScore"
    )
    assert strings["get_custom_position_score_registration_name"][
        "reference_instruction_rva"
    ] == "0x0028cf9f"


def test_native_call_edges_reach_both_integer_converters():
    edges = {item["id"]: item for item in _load()["call_edges"]}
    assert edges["danger_member_to_prefixed_getter"] == {
        "id": "danger_member_to_prefixed_getter",
        "instruction_rva": "0x0023981f",
        "target_rva": "0x00049290",
        "instruction_hex": "e86cfae0ff",
    }
    assert edges["prefixed_getter_to_no_argument_wrapper"]["target_rva"] == (
        "0x000494c0"
    )
    assert edges["custom_member_to_named_lookup"]["target_rva"] == (
        "0x00049350"
    )
    assert edges["custom_member_to_point_wrapper"]["target_rva"] == (
        "0x00244380"
    )
    assert edges["no_argument_wrapper_to_integer_conversion"][
        "target_rva"
    ] == "0x000499d0"
    assert edges["point_wrapper_to_integer_conversion"]["target_rva"] == (
        "0x00244510"
    )


def test_stock_replay_resolves_inherited_values_without_rounding_input():
    result = replay_stock_enemy_position_score_helpers()
    assert result == {
        "replay_kind": "stock_enemy_position_score_helpers_replay",
        "scope": "unmodified shipped Lua Pawn definitions",
        "danger_score": {
            "native_binding": "Pawn:GetDangerScore",
            "lua_method": "GetScoreDanger",
            "field": "ScoreDanger",
            "lua_value": -10,
            "native_integer": -10,
        },
        "custom_position_score": {
            "native_binding": "Pawn:GetCustomPositionScore",
            "lua_method": "GetPositionScore",
            "argument": "candidate Point",
            "field": "PositionScore",
            "lua_value": 0,
            "native_integer": 0,
        },
        "x87_rounding_invariant": True,
    }
    assert _load()["replay_vectors"][0]["expected"] == result


def test_contract_does_not_hide_runtime_or_modded_mutation_scope():
    value = _load()
    assert value["contracts"]["unmodified_shipped_danger_score"] == -10
    assert value["contracts"]["unmodified_shipped_custom_position_score"] == 0
    assert value["contracts"]["stock_defaults_require_runtime_rounding_mode"] is False
    assert value["closure"]["runtime_or_modded_field_mutation_complete"] is False
    assert value["unresolved"][0]["id"] == "runtime_or_modded_field_mutation"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["source_regions"][0].update(
                {"body_sha256": "0" * 64}
            ),
            "fields differ",
        ),
        (
            lambda value: value["native_regions"][3].update({"size": 58}),
            "fields differ",
        ),
        (
            lambda value: value["native_strings"][1].update(
                {"value": "CustomMoveScore"}
            ),
            "fields differ",
        ),
        (
            lambda value: value["replay_vectors"][0]["expected"][
                "custom_position_score"
            ].update({"native_integer": 1}),
            "fields differ",
        ),
    ],
)
def test_binding_rejects_source_native_literal_and_replay_drift(mutate, message):
    altered = copy.deepcopy(_load())
    mutate(altered)
    with pytest.raises(EnemyPositionScoreHelpersBoundaryError, match=message):
        validate_enemy_position_score_helpers_boundary_binding(altered)


def test_inventory_binding_and_encoding_fail_closed():
    inventory = _load(INVENTORY)
    altered = copy.deepcopy(inventory)
    altered["steam"]["build_id"] = "different"
    with pytest.raises(
        EnemyPositionScoreHelpersBoundaryError,
        match="inventory fields differ",
    ):
        build_enemy_position_score_helpers_boundary(CONTENT_ROOT, altered)

    value = _load()
    encoded = encode_enemy_position_score_helpers_boundary(value)
    assert encoded.endswith("\n")
    assert json.loads(encoded) == value
    assert encoded == encode_enemy_position_score_helpers_boundary(value)


def test_exact_install_rebuilds_executable_dll_and_shipped_source_join_when_available():
    if not (CONTENT_ROOT / "Breach.exe").is_file():
        pytest.skip("exact local ITB installation is not available")

    result = validate_enemy_position_score_helpers_boundary(
        CONTENT_ROOT,
        _load(INVENTORY),
        _load(),
    )
    assert result["status"] == "verified"
    assert result["native_helper_call_paths_complete"] is True
    assert result["shipped_source_default_census_complete"] is True
    assert result["unmodified_shipped_results_complete"] is True
    assert result["simulator_change_required"] is False
