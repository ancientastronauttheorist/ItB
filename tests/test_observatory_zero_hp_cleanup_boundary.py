from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.zero_hp_cleanup_boundary import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    ZeroHpCleanupBoundaryError,
    validate_zero_hp_cleanup_boundary_map,
    validate_zero_hp_cleanup_boundary_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CLEANUP_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_zero_hp_cleanup_boundary.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(CLEANUP_MAP.read_text(encoding="utf-8"))


def test_committed_map_proves_conditional_cleanup_without_timing_or_credit_overclaim():
    value = _load()
    result = validate_zero_hp_cleanup_boundary_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["conditional_dead_noncorpse_board_erase_proven"] is True
    assert result["exact_cleanup_timing_proven"] is False
    assert result["callback_or_credit_tail_proven"] is False
    assert result["simulator_change_required"] is False
    assert result["artifact_sha256"] == (
        "bf9713a2b46c524373599666c5113c09"
        "95bd841411d777d3a810895be1a03064"
    )
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256

    cleanup = value["contracts"]["board_cleanup"]
    assert cleanup["exact_direct_caller_rvas"] == ["0x0016ae58", "0x001e9fb5"]
    assert cleanup["candidate_state_byte_offsets_required_zero"] == [
        "+0x1325",
        "+0x0922",
        "+0x0921",
    ]
    assert cleanup["requires_virtual_is_dead"] is True
    assert cleanup["direct_is_corpse_call"] is True
    assert cleanup["required_is_corpse_result"] is False
    assert cleanup["pawn_byte_offset_required_zero"] == "+0x0964"
    assert cleanup["pawn_vector_begin_offset"] == "+0x00a0"
    assert cleanup["pawn_vector_end_offset"] == "+0x00a4"
    assert cleanup["vector_end_decrement_bytes"] == 4
    assert cleanup["exact_damage_relative_timing_proven"] is False

    corpse = value["contracts"]["corpse_join"]
    assert corpse == {
        "corpse_true_skips_reviewed_erase": True,
        "is_corpse_is_nontrivial_predicate": True,
        "retained_corpse_counts_path_occupancy": True,
        "retained_dead_noncorpse_counts_path_occupancy": False,
        "subclass_results_exhausted": False,
    }
    callback = value["contracts"]["callback_and_credit"]
    assert callback["absolute_onkill_reference_count"] == 4
    assert callback["onkill_reference_function_count"] == 2
    assert callback["event_enemy_killed_name_reference_count"] == 1
    assert callback["lua_onkill_dispatch_proven"] is False
    assert callback["kill_credit_or_owner_attribution_proven"] is False
    assert callback["mission_or_achievement_counter_update_proven"] is False

    references = {
        item["id"]: item for item in value["absolute_reference_inventory"]
    }
    assert len(references["on_kill_name"]["references"]) == 4
    assert len(references["event_enemy_killed_name"]["references"]) == 1
    assert {item["id"] for item in value["unresolved"]} == {
        "cleanup_scheduler_timing",
        "subclass_death_and_corpse_results",
        "on_kill_callback_dispatch",
        "kill_credit_and_owner_attribution",
        "death_effect_and_presentation_tail",
        "non_windows_equivalence",
    }


def test_binding_rejects_cleanup_reference_or_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["board_cleanup"]["required_is_corpse_result"] = True
    with pytest.raises(ZeroHpCleanupBoundaryError, match="fields differ"):
        validate_zero_hp_cleanup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["absolute_reference_inventory"][-2]["references"].pop()
    with pytest.raises(ZeroHpCleanupBoundaryError, match="fields differ"):
        validate_zero_hp_cleanup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["callback_and_credit"]["lua_onkill_dispatch_proven"] = True
    with pytest.raises(ZeroHpCleanupBoundaryError, match="fields differ"):
        validate_zero_hp_cleanup_boundary_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_change_required"] = True
    with pytest.raises(ZeroHpCleanupBoundaryError, match="fields differ"):
        validate_zero_hp_cleanup_boundary_map_binding(altered)


def test_exact_local_executable_sources_and_dependencies_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_zero_hp_cleanup_boundary_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["conditional_dead_noncorpse_board_erase_proven"] is True
    assert result["exact_cleanup_timing_proven"] is False
    assert result["callback_or_credit_tail_proven"] is False
    assert result["simulator_change_required"] is False
