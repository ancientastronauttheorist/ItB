from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_map_choice import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveMapChoiceError,
    validate_final_cave_map_choice_map,
    validate_final_cave_map_choice_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
MAP_CHOICE = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_map_choice.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(MAP_CHOICE.read_text(encoding="utf-8"))


def test_committed_map_closes_random_map_and_random_int_one_boundaries():
    value = _load()
    result = validate_final_cave_map_choice_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "8068a847b328ba8137ff9c88864f66ea"
            "aa0bf93c5f8ba34aedd1b4115e7936db"
        ),
        "random_map_algorithm_proven": True,
        "candidate_order_installation_bound": True,
        "random_int_one_advancement_proven": True,
        "ordinary_first_transition_draw_count": 2,
        "concrete_map_forecast_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["supersedes"] == {
        "artifact": (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_cave_startup.json"
        ),
        "artifact_sha256": (
            "4cf2f05a267ed87a8cf5b14edbc87434"
            "3a3969cef2dfb98e849f645ec177f942"
        ),
        "resolved_gap_ids": ["native_random_map"],
        "narrowed_gap_ids": ["native_rng_state"],
        "correction": (
            "The immutable startup artifact correctly left random_int(1) "
            "open. Exact PE evidence now proves it advances one RNG step."
        ),
    }
    assert value["summary"] == {
        "reviewed_source_count": 5,
        "region_count": 9,
        "string_anchor_count": 6,
        "data_anchor_count": 3,
        "control_window_count": 11,
        "call_edge_count": 8,
        "candidate_count": 9,
        "finding_count": 7,
        "unresolved_count": 3,
        "random_map_algorithm_proven": True,
        "candidate_order_installation_bound": True,
        "advanced_edition_filter_absent": True,
        "random_int_one_advancement_proven": True,
        "ordinary_first_transition_draw_count": 2,
        "concrete_map_forecast_proven": False,
        "simulator_change_required": False,
    }

    contract = value["random_map_contract"]
    candidates = contract["candidate_order"]
    assert [item["map_name"] for item in candidates] == [
        "cave1",
        "cave2",
        "cave3",
        "cave4",
        "cave5",
        "caveAE1",
        "caveAE2",
        "caveAE3",
        "caveAE4",
    ]
    assert [item["rng_remainder"] for item in candidates] == list(range(9))
    assert contract["advanced_edition_filter_present"] is False
    assert contract["mission_map_vetoes"] == []
    assert contract["ordinary_first_transition_attempts"] == 1

    draws = value["rng_contract"][
        "ordinary_first_transition_draws_before_environment"
    ]
    assert draws[0] == {
        "ordinal": 1,
        "source": "Mission:GetMapTag -> random_element(MapTags)",
        "max": 1,
        "advances_rng": True,
        "result": 0,
        "semantic_result": "final_cave",
    }
    assert draws[1]["max"] == 9
    assert draws[1]["result"] == "second_rng_output % 9"


def test_binding_rejects_order_rng_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["map_registration"]["directory_order_sha256"] = "0" * 64
    with pytest.raises(FinalCaveMapChoiceError, match="fields differ"):
        validate_final_cave_map_choice_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["random_map_contract"]["candidate_order"].reverse()
    with pytest.raises(FinalCaveMapChoiceError, match="fields differ"):
        validate_final_cave_map_choice_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["rng_contract"][
        "ordinary_first_transition_draws_before_environment"
    ][0]["advances_rng"] = False
    with pytest.raises(FinalCaveMapChoiceError, match="fields differ"):
        validate_final_cave_map_choice_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalCaveMapChoiceError, match="fields differ"):
        validate_final_cave_map_choice_map_binding(altered)


def test_exact_local_build_and_installation_order_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_map_choice_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["random_int_one_advancement_proven"] is True
    assert result["ordinary_first_transition_draw_count"] == 2
    assert result["concrete_map_forecast_proven"] is False
