from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.observatory.specialized_enemy_death_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    SpecializedEnemyDeathBoundaryError,
    validate_specialized_enemy_death_boundary_map,
    validate_specialized_enemy_death_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_"
    "specialized_enemy_death_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_specialized_enemy_death_classes():
    value = _load()
    result = validate_specialized_enemy_death_boundary_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["generic_factory_path_proven"] is True
    assert result["specialized_enemy_death_classes_proven"] is True
    assert result["active_minor_type_count"] == 17
    assert result["boss_objective_type_count"] == 21
    assert result["simulator_contradiction_found"] is True
    assert result["simulator_change_applied"] is True
    assert result["simulator_version"] == 407
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256

    assert value["summary"] == {
        "active_minor_type_count": 17,
        "boss_objective_type_count": 21,
        "call_inventory_count": 3,
        "control_window_count": 12,
        "data_anchor_count": 1,
        "dependency_count": 1,
        "direct_edge_count": 6,
        "finding_count": 7,
        "generic_factory_path_proven": True,
        "minor_boss_auxiliary_type_count": 4,
        "region_count": 8,
        "simulator_change_applied": True,
        "simulator_contradiction_found": True,
        "simulator_version": 407,
        "source_count": 15,
        "specialized_enemy_death_classes_proven": True,
        "unresolved_count": 3,
    }

    factory = value["contracts"]["generic_factory_path"]
    assert factory["wrapper_team_selector"] == 2
    assert factory["team_lookup_name"] == "GetDefaultTeam"
    assert factory["allocated_object_size"] == 0x1328
    assert factory["common_pawn_vtable_va"] == "0x0082e320"
    assert factory["is_mech_default"] is False
    assert factory["minor_default"] is False
    assert factory["hidden_boss_subclass_on_reviewed_path"] is False

    predicate = value["contracts"]["ordinary_enemy_event_predicate"]
    assert predicate["event_2_id"] == 2
    assert predicate["event_2_required_is_mech_value"] is False
    assert predicate["event_2_required_team_value"] == 6
    assert predicate["event_2_required_minor_value"] is False
    assert predicate["minor_enemy_event_id"] == 12
    assert predicate["leader_flag_is_a_gate"] is False
    assert predicate["tier_flag_is_a_gate"] is False
    assert predicate["pawn_type_name_is_a_gate"] is False

    inventory = value["source_inventory"]
    assert len(inventory["active_minor_types"]) == 17
    assert len(inventory["boss_objective_types"]) == 21
    assert not set(inventory["active_minor_types"]) & set(
        inventory["boss_objective_types"]
    )
    assert inventory["minor_derived_child_types"] == []
    assert inventory["minor_boss_auxiliary_types"] == [
        "BlobB",
        "TotemB",
        "SlugEgg1",
        "SpiderlingEgg1",
    ]
    assert inventory["blob_boss_counting_forms"] == [
        "BlobBoss",
        "BlobBossMed",
        "BlobBossSmall",
    ]
    assert inventory["set_team_enemy_occurrences"] == []
    assert inventory["enemy_team_mech_construction_reachable_in_shipped_lua"] is False


def test_binding_rejects_factory_predicate_inventory_or_solver_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["generic_factory_path"]["allocated_object_size"] = 0x1324
    with pytest.raises(SpecializedEnemyDeathBoundaryError, match="fields differ"):
        validate_specialized_enemy_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["ordinary_enemy_event_predicate"][
        "event_2_required_is_mech_value"
    ] = True
    with pytest.raises(SpecializedEnemyDeathBoundaryError, match="fields differ"):
        validate_specialized_enemy_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["source_inventory"]["active_minor_types"].remove("BlobB")
    with pytest.raises(SpecializedEnemyDeathBoundaryError, match="fields differ"):
        validate_specialized_enemy_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_version"] = 406
    with pytest.raises(SpecializedEnemyDeathBoundaryError, match="fields differ"):
        validate_specialized_enemy_death_boundary_map_binding(altered)


def test_v407_solver_predicate_bridge_fields_and_archive_are_bound():
    board = (ROOT / "rust_solver" / "src" / "board.rs").read_text(encoding="utf-8")
    rust_lib = (ROOT / "rust_solver" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    verify = (ROOT / "src" / "solver" / "verify.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
        encoding="utf-8"
    )

    assert "!unit.is_enemy() || unit.is_mech() || unit.minor()" in board
    assert "pub const SIMULATOR_VERSION: u32 = 408;" in rust_lib
    assert "SIMULATOR_VERSION = 408" in verify
    assert "team = p:GetTeam()," in bridge
    assert "mech = p:IsMech()," in bridge
    assert "minor = pawn_def and pawn_def.Minor or false," in bridge

    archive = ROOT / "recordings" / "failure_db_snapshot_sim_v406.jsonl"
    assert archive.stat().st_size == 5_950_022
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "c3ec8cb98534ddb8a394dd860851bf123d6cd502d676651a11692c3d9576dfc8"
    )


def test_exact_local_executable_source_and_dependency_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_specialized_enemy_death_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["generic_factory_path_proven"] is True
    assert result["specialized_enemy_death_classes_proven"] is True
    assert result["simulator_change_applied"] is True
    assert result["simulator_version"] == 407
