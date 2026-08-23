from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_replacement import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveReplacementError,
    validate_final_cave_replacement_map,
    validate_final_cave_replacement_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
REPLACEMENT_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_replacement.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(REPLACEMENT_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_replacement_materialization_path_without_rng_overclaim():
    value = _load()
    result = validate_final_cave_replacement_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "b08b6d96d4d4ba0f53c024b301b17a03"
            "9c8deb944632bbc6b8b4000a6e20af50"
        ),
        "replacement_materialization_path_proven": True,
        "callback_to_queue_order_proven": True,
        "add_dropper_copy_semantics_proven": True,
        "concrete_coordinate_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 3,
        "region_count": 28,
        "string_anchor_count": 6,
        "data_pointer_count": 5,
        "control_window_count": 20,
        "direct_edge_count": 19,
        "finding_count": 9,
        "unresolved_count": 3,
        "replacement_materialization_path_proven": True,
        "callback_to_queue_order_proven": True,
        "add_dropper_copy_semantics_proven": True,
        "concrete_coordinate_proven": False,
        "simulator_change_required": False,
    }
    assert value["supersedes"]["resolved_gap_ids"] == [
        "replacement_materialization"
    ]
    assert value["supersedes"]["split_remaining_gap_ids"] == [
        "replacement_coordinate_and_draw_count",
        "replacement_uid_timing_and_repeat_cadence",
    ]

    selection = value["contracts"]["candidate_selection"]
    assert selection["enumeration"] == (
        "x=0..7 outer loop, y=0..7 inner loop"
    )
    assert selection["empty_fallback"] == [4, 4]
    assert selection["concrete_draw_count_known"] is False
    assert selection["concrete_coordinate_known"] is False

    record = value["contracts"]["dropper_record"]
    assert record["space_damage_size"] == "0x134"
    assert record["kind_offset"] == "0x98"
    assert record["dropper_kind"] == 4
    assert record["source_s_pawn"] == "BigBomb"
    assert record["copied_during_add_dropper"] is True
    assert record["later_lua_mutation_affects_stored_record"] is False

    order = value["contracts"]["native_relative_order"]
    assert order["same_board_update_dispatch_possible"] is False
    assert order["earliest_dispatch"] == (
        "a later eligible Board effect update"
    )
    assert order["queued_effect_activity_reason"] == 6
    assert order["immediate_repeat_while_queue_nonempty"] is False

    materialization = value["contracts"]["materialization_path"]
    assert materialization["record_dispatch"] == (
        "kind 4 -> PylonAnimation"
    )
    assert materialization["stored_space_damage_offset"] == "0x2dc"
    assert materialization["spawn_guard"] == (
        "SpaceDamage.sPawn length is nonzero"
    )
    assert materialization["source_result"] == (
        "BigBomb is added at the selected AddBomb point"
    )

    findings = {item["id"]: item for item in value["findings"]}
    assert "cannot dispatch in the same" in findings[
        "board_update_precedes_replacement_callback"
    ]["claim"]
    assert "Later mutation" in findings[
        "add_dropper_copy_semantics_are_exact"
    ]["claim"]
    assert "selected point materializes a BigBomb" in findings[
        "bigbomb_drop_resolution_path_is_exact"
    ]["claim"]
    assert "No Rust simulator semantic change" in findings[
        "solver_boundary"
    ]["claim"]

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "replacement_coordinate_and_draw_count",
        "replacement_uid_timing_and_repeat_cadence",
        "non_windows_equivalence",
    }


def test_binding_rejects_pointer_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["data_pointers"][0]["target_rva"] = "0x00000000"
    with pytest.raises(FinalCaveReplacementError, match="fields differ"):
        validate_final_cave_replacement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["sha256"] = "0" * 64
    with pytest.raises(FinalCaveReplacementError, match="fields differ"):
        validate_final_cave_replacement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalCaveReplacementError, match="fields differ"):
        validate_final_cave_replacement_map_binding(altered)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_replacement_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["replacement_materialization_path_proven"] is True
    assert result["callback_to_queue_order_proven"] is True
    assert result["add_dropper_copy_semantics_proven"] is True
    assert result["concrete_coordinate_proven"] is False
    assert result["simulator_change_required"] is False
