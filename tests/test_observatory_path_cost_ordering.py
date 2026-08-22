from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.path_cost_ordering import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    PathCostOrderingError,
    validate_path_cost_ordering_map,
    validate_path_cost_ordering_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
PATH_COST_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_path_cost_ordering.json"
)


def _load() -> dict:
    return json.loads(PATH_COST_MAP.read_text(encoding="utf-8"))


def test_committed_path_cost_map_pins_native_costs_ordering_and_massive_water():
    value = _load()
    result = validate_path_cost_ordering_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["reachable_edge_cost"] == 1
    assert result["reachable_output_order"] == ["x", "y"]
    assert result["path_heuristic_weight"] == pytest.approx(1.01)
    assert result["massive_water_transit"] is True
    assert result["massive_water_stop"] is True
    assert result["simulator_version"] == 402
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "control_window_count": 14,
        "direction_order": [[0, -1], [1, 0], [0, 1], [-1, 0]],
        "massive_water_stop": True,
        "massive_water_transit": True,
        "ordinary_occupancy_team_agnostic": True,
        "path_heuristic_weight": pytest.approx(1.01),
        "path_includes_both_endpoints": True,
        "path_priority_order": ["f", "x", "y"],
        "reachable_edge_cost": 1,
        "reachable_output_order": ["x", "y"],
        "region_count": 26,
        "remaining_runtime_proof": [
            "matched native GetReachable and GetPath output vectors",
            "dead pawn and corpse occupancy classification",
            "AddMove step effects, interruption, and scheduler timing",
            "non-Windows build equivalence",
        ],
        "simulator_version": 402,
    }


def test_path_cost_map_binding_rejects_order_or_water_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["ordering"]["reachable_output_order"] = ["y", "x"]
    with pytest.raises(PathCostOrderingError, match="fields differ"):
        validate_path_cost_ordering_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["terrain_3_water"]["path_massive_2_can_transit"] = False
    with pytest.raises(PathCostOrderingError, match="fields differ"):
        validate_path_cost_ordering_map_binding(altered)


def test_exact_local_executable_reproduces_path_cost_map_when_available():
    executable = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_path_cost_ordering_map(executable, _load())
    assert result["status"] == "verified"
