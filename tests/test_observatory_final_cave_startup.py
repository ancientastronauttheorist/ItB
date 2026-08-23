from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_startup import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveStartupError,
    validate_final_cave_startup_map,
    validate_final_cave_startup_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
STARTUP_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_startup.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(STARTUP_MAP.read_text(encoding="utf-8"))


def test_committed_map_pins_startup_pool_and_rng_skeleton_without_outputs():
    value = _load()
    result = validate_final_cave_startup_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "4cf2f05a267ed87a8cf5b14edbc87434"
            "3a3969cef2dfb98e849f645ec177f942"
        ),
        "relative_startup_order_proven": True,
        "map_pool_proven": True,
        "lua_rng_call_skeleton_proven": True,
        "concrete_rng_outputs_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 6,
        "final_cave_map_count": 9,
        "region_count": 6,
        "string_anchor_count": 7,
        "control_window_count": 5,
        "direct_edge_count": 5,
        "finding_count": 6,
        "unresolved_count": 5,
        "relative_startup_order_proven": True,
        "map_pool_proven": True,
        "lua_rng_call_skeleton_proven": True,
        "concrete_rng_outputs_proven": False,
        "effect_settlement_timing_proven": False,
        "simulator_change_required": False,
    }

    contract = value["startup_contract"]
    assert contract["native_order"] == [
        "GAME.CreateNextPhase",
        "map selection",
        "map loading/AddMap",
        "intermediate board initialization",
        "mission BaseStart",
    ]
    assert contract["bomb_and_mech_assignment_permutations"] == 24
    assert set(contract["mountain_drop_counts"].values()) == {3, 4}
    assert contract["boss_candidates"] == [
        "BeetleBoss",
        "FireflyBoss",
        "HornetBoss",
    ]

    assert len(value["sources"]["maps"]) == 9
    assert {
        tuple(point)
        for entry in value["sources"]["maps"]
        for point in entry["zones"]["deployment"]
    } == {(3, 3), (3, 4), (2, 4), (2, 3)}
    assert [entry["order"] for entry in value["rng_schedule"]] == list(
        range(1, 13)
    )

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "native_random_map",
        "native_rng_state",
        "environment_path_result",
        "spawn_selection_and_coordinates",
        "startup_effect_settlement",
    }


def test_binding_rejects_native_map_rng_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["direct_call_edges"][0]["instruction_hex"] = "90"
    with pytest.raises(FinalCaveStartupError, match="fields differ"):
        validate_final_cave_startup_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["maps"][0]["zones"]["pylons"].pop()
    with pytest.raises(FinalCaveStartupError, match="fields differ"):
        validate_final_cave_startup_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["rng_schedule"][4]["bounds"] = [3]
    with pytest.raises(FinalCaveStartupError, match="fields differ"):
        validate_final_cave_startup_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalCaveStartupError, match="fields differ"):
        validate_final_cave_startup_map_binding(altered)


def test_exact_local_build_sources_and_maps_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_startup_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["relative_startup_order_proven"] is True
    assert result["map_pool_proven"] is True
    assert result["concrete_rng_outputs_proven"] is False
