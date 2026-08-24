from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from src.model.pawn_stats import get_pawn_stats
from src.observatory.corpse_classification_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    CorpseClassificationBoundaryError,
    validate_corpse_classification_boundary_map,
    validate_corpse_classification_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_"
    "corpse_classification_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")

EFFECTIVE_CORPSE_TYPES = {
    "ArchiveArtillery",
    "Dam_Pawn",
    "Filler_Pawn",
    "Pawn_Laser_D",
    "Pawn_Laser_L",
    "Pawn_Laser_R",
    "Pawn_Laser_U",
    "Pawn_Piston_D",
    "Pawn_Piston_L",
    "Pawn_Piston_R",
    "Pawn_Piston_U",
    "SatelliteRocket",
    "Train_Armored",
    "Train_Armored_Damaged",
    "Train_Damaged",
    "Train_Pawn",
}


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_static_corpse_classification_without_timing_overclaim():
    value = _load()
    result = validate_corpse_classification_boundary_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["common_predicate_proven"] is True
    assert result["mutation_12_identity_proven"] is True
    assert result["effective_corpse_type_count"] == 16
    assert result["shipped_mutation_12_reachable"] is False
    assert result["simulator_contradiction_found"] is False
    assert result["simulator_change_required"] is False
    assert result["simulator_version"] == 407
    assert result["artifact_sha256"] == (
        "401eefc2bd6b59f70861cc1c7bc35d4a"
        "67597d2d621cd18655f8dcac285abe6e"
    )
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256

    assert value["summary"] == {
        "call_inventory_count": 3,
        "common_predicate_proven": True,
        "control_window_count": 10,
        "data_anchor_count": 8,
        "dependency_count": 2,
        "direct_edge_count": 1,
        "effective_corpse_type_count": 16,
        "explicit_corpse_type_count": 10,
        "finding_count": 6,
        "inherited_corpse_type_count": 6,
        "mutation_12_identity_proven": True,
        "region_count": 6,
        "shipped_mutation_12_reachable": False,
        "simulator_change_required": False,
        "simulator_contradiction_found": False,
        "simulator_version": 407,
        "source_count": 13,
        "unresolved_count": 2,
    }

    predicate = value["contracts"]["common_predicate"]
    assert predicate["native_rva"] == "0x0022cde0"
    assert predicate["single_common_member"] is True
    assert predicate["subclass_vtable_dispatch_inside_predicate"] is False
    assert predicate["complete_direct_call_count"] == 27
    assert predicate["source_corpse_field_offset"] == "0x0f80"
    assert predicate["is_mech_field_offset"] == "0x09e4"
    assert predicate["internal_lifecycle_state_offset"] == "0x09e0"
    assert predicate["mutation_field_offset"] == "0x10e8"
    assert predicate["special_lifecycle_states"] == [2, 3, 4]
    assert predicate["required_mutation_id_for_special_states"] == 12

    mutation = value["contracts"]["mutation_12_eligibility"]
    assert mutation["registered_name"] == "LEADER_NECRO"
    assert mutation["registered_value"] == 12
    assert mutation["current_mutation_setter_name"] == "SetMutation"
    assert mutation["leader_field_offset"] == "0x1318"
    assert mutation["minor_field_offset"] == "0x10d0"
    assert mutation["alternate_recipient_passive"] == "Psion_Leech"
    assert mutation["teleporter_is_an_input"] is False

    reachability = value["contracts"]["shipped_reachability"]
    assert reachability["jelly_necro_table_defined"] is True
    assert reachability["jelly_necro_other_active_lua_references"] == 0
    assert reachability["shipped_lua_set_mutation_calls"] == 0
    assert reachability["mutation_12_reachable_from_accepted_shipped_lua"] is False

    inventory = value["source_inventory"]
    assert set(inventory["effective_corpse_types"]) == EFFECTIVE_CORPSE_TYPES
    assert inventory["explicit_type_count"] == 10
    assert inventory["inherited_type_count"] == 6
    assert inventory["effective_type_count"] == 16
    assert {item["pawn_type"] for item in inventory["inherited_corpse_types"]} == {
        "Pawn_Laser_D",
        "Pawn_Laser_L",
        "Pawn_Laser_R",
        "Pawn_Piston_D",
        "Pawn_Piston_L",
        "Pawn_Piston_R",
    }
    assert {item["id"] for item in value["unresolved"]} == {
        "lifecycle_state_transition_timing",
        "mission_piston_action_order",
    }
    assert value["refines"][0]["narrowed_unresolved_id"] == (
        "subclass_death_and_corpse_results"
    )
    assert value["solver_impact"] == {
        "reason": (
            "The bridge exports current and static corpse state, and Python "
            "plus Rust already cover every effective shipped corpse type."
        ),
        "simulator_change_required": False,
        "simulator_contradiction_found": False,
        "simulator_version": 407,
        "simulator_version_bump_required": False,
    }


def test_binding_rejects_predicate_mutation_inventory_or_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["common_predicate"]["special_lifecycle_states"] = [2, 3]
    with pytest.raises(CorpseClassificationBoundaryError, match="fields differ"):
        validate_corpse_classification_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["mutation_12_eligibility"]["registered_name"] = (
        "LEADER_TELEPORT"
    )
    with pytest.raises(CorpseClassificationBoundaryError, match="fields differ"):
        validate_corpse_classification_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["source_inventory"]["effective_corpse_types"].remove("Dam_Pawn")
    with pytest.raises(CorpseClassificationBoundaryError, match="fields differ"):
        validate_corpse_classification_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["summary"]["simulator_change_required"] = True
    with pytest.raises(CorpseClassificationBoundaryError, match="fields differ"):
        validate_corpse_classification_boundary_map_binding(altered)


def test_solver_inventory_bridge_fields_version_and_piston_gate_conform():
    rust = (ROOT / "rust_solver" / "src" / "serde_bridge.rs").read_text(
        encoding="utf-8"
    )
    rust_inventory = rust[
        rust.index("fn known_corpse_on_death_type") : rust.index(
            "#[derive(Deserialize)]", rust.index("fn known_corpse_on_death_type")
        )
    ]
    bridge = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
        encoding="utf-8"
    )
    commands = (ROOT / "src" / "loop" / "commands.py").read_text(
        encoding="utf-8"
    )
    rust_lib = (ROOT / "rust_solver" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    verify = (ROOT / "src" / "solver" / "verify.py").read_text(
        encoding="utf-8"
    )

    for pawn_type in EFFECTIVE_CORPSE_TYPES:
        assert get_pawn_stats(pawn_type).corpse_on_death is True, pawn_type
        assert f'"{pawn_type}"' in rust_inventory, pawn_type

    quoted_rust_types = set(re.findall(r'"([A-Za-z0-9_]+)"', rust_inventory))
    assert quoted_rust_types == EFFECTIVE_CORPSE_TYPES
    assert "pcall(function() return p:IsCorpse() end)" in bridge
    assert "corpse = current_corpse" in bridge
    assert "pawn_def and pawn_def.Corpse == true or false" in bridge
    assert "corpse_on_death = corpse_on_death" in bridge
    assert "mission_piston_corpse_lifecycle_unknown" not in commands
    assert "mission_piston_state_unknown" in commands
    assert "pub const SIMULATOR_VERSION: u32 = 408;" in rust_lib
    assert "SIMULATOR_VERSION = 408" in verify


def test_exact_local_executable_sources_and_dependencies_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_corpse_classification_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["common_predicate_proven"] is True
    assert result["mutation_12_identity_proven"] is True
    assert result["shipped_mutation_12_reachable"] is False
    assert result["simulator_change_required"] is False
    assert result["simulator_version"] == 407
