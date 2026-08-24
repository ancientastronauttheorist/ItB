from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.damage_death_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    DamageDeathBoundaryError,
    validate_damage_death_boundary_map,
    validate_damage_death_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_damage_death_pawn_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(BOUNDARY_MAP.read_text(encoding="utf-8"))


def test_committed_map_proves_hp_zero_boundary_without_callback_overclaim():
    value = _load()
    result = validate_damage_death_boundary_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "e9a1a70eae208851cb62bc2e022c9782"
            "5a889beffa6322c02dfb7668c0de1af3"
        ),
        "hp_zero_boundary_proven": True,
        "callback_or_credit_tail_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "source_count": 2,
        "region_count": 15,
        "data_anchor_count": 6,
        "method_binding_count": 3,
        "control_window_count": 16,
        "direct_edge_count": 8,
        "finding_count": 7,
        "unresolved_count": 5,
        "hp_zero_boundary_proven": True,
        "callback_or_credit_tail_proven": False,
        "simulator_change_required": False,
    }

    sentinel = value["contracts"]["sentinel"]
    assert sentinel["native_integer"] == 1000
    assert sentinel["record_offset"] == "+0x08"
    statuses = value["contracts"]["pawn_status_order"]
    assert statuses["shield_zeroes_damage_1000"] is False
    assert statuses["frozen_zeroes_damage_1000"] is False
    assert statuses["armored_damage_from_1000"] == 999
    assert statuses["acid_armored_damage_from_1000"] == 1998
    assert statuses["flight_test_in_generic_receiver"] is False
    assert statuses["massive_test_in_generic_receiver"] is False

    handoff = value["contracts"]["hp_handoff"]
    assert handoff["receiver_argument"] == "negative effective damage"
    assert handoff["negative_delta_floor"] == "minus current HP"
    assert handoff["proven_terminal_boundary"] == "HP reaches zero"
    assert handoff["direct_pawn_kill_call_in_receiver_to_hp_chain"] is False
    assert handoff["separate_building_terrain_pawn_kill_call"] is True

    scope = value["contracts"]["scope_limit"]
    assert all(proven is False for proven in scope.values())
    assert {item["id"] for item in value["unresolved"]} == {
        "zero_hp_corpse_and_removal_timing",
        "on_kill_callback_dispatch",
        "kill_credit_and_owner_attribution",
        "specialized_pawn_subclass_tail",
        "non_windows_equivalence",
    }
    assert {item["id"] for item in value["direct_edges"]} == {
        "apply_calls_damage_core",
        "core_calls_pawn_receiver",
        "receiver_queries_armor",
        "receiver_clears_shield",
        "receiver_clears_frozen",
        "receiver_calls_hp_delta",
        "hp_delta_calls_value_bar",
        "building_terrain_branch_calls_pawn_kill",
    }


def test_binding_rejects_native_or_claim_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["sentinel"]["native_integer"] = 999
    with pytest.raises(DamageDeathBoundaryError, match="fields differ"):
        validate_damage_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["scope_limit"]["lua_on_kill_dispatch_proven"] = True
    with pytest.raises(DamageDeathBoundaryError, match="fields differ"):
        validate_damage_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["direct_edges"][-1]["from_rva"] = "0x001adca3"
    with pytest.raises(DamageDeathBoundaryError, match="fields differ"):
        validate_damage_death_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][4]["claim"] += " overclaim"
    with pytest.raises(DamageDeathBoundaryError, match="fields differ"):
        validate_damage_death_boundary_map_binding(altered)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_damage_death_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["hp_zero_boundary_proven"] is True
    assert result["callback_or_credit_tail_proven"] is False
    assert result["simulator_change_required"] is False
