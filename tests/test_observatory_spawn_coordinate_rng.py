from __future__ import annotations

from copy import deepcopy

import pytest

from src.observatory.spawn_coordinate_rng import (
    CALLER_SPECS,
    SpawnCoordinateRngError,
    compare_spawn_coordinate_rng_attributions,
    explain_spawn_coordinate_rng_variation,
    match_spawn_coordinate_rng_records,
)


def _return_map() -> dict:
    callers = []
    for caller_id in range(1, 67):
        callers.append(
            {
                "caller_id": caller_id,
                "call_rva": f"0x{caller_id:08x}",
                "return_rva": f"0x{caller_id + 5:08x}",
                "classification": {
                    "status": "unclassified_raw_candidate",
                    "source_region": None,
                    "edge_id": None,
                    "meaning": None,
                },
            }
        )
    for spec in CALLER_SPECS.values():
        callers[spec["caller_id"] - 1].update(
            call_rva=spec["call_rva"], return_rva=spec["return_rva"]
        )
    return {"callers": callers}


def _rng_records() -> list[dict]:
    return [
        {"kind": "rng_core", "seq": 0, "thread_slot": 0, "caller_id": 21, "result": 7},
        {"kind": "rng_core", "seq": 1, "thread_slot": 0, "caller_id": 66, "result": 5},
        {"kind": "rng_core", "seq": 2, "thread_slot": 0, "caller_id": 21, "result": 8},
        {"kind": "rng_core", "seq": 3, "thread_slot": 0, "caller_id": 60, "result": 4},
        {"kind": "rng_core", "seq": 4, "thread_slot": 0, "caller_id": 25, "result": 9},
    ]


def _events() -> list[dict]:
    return [
        {
            "kind": "scheduler_draw",
            "seq": 0,
            "raw_rng": 5,
            "candidate_count": 3,
            "selected_index": 2,
            "selected": [3, 3],
            "candidates": [[1, 1], [2, 2], [3, 3]],
        },
        {
            "kind": "selector_standard_draw",
            "seq": 1,
            "raw_rng": 4,
            "candidate_count": 2,
            "selected_index": 0,
            "selected": [5, 3],
            "candidates": [[5, 3], [6, 5]],
        },
    ]


def test_exact_direct_callers_resolve_coordinate_rng_ordinals():
    result = match_spawn_coordinate_rng_records(
        _rng_records(), _events(), return_map=_return_map()
    )

    assert [item["caller_id"] for item in result] == [66, 60]
    assert [item["rng_ordinal"] for item in result] == [2, 4]
    assert result[1]["upstream_caller_counts"] == {"21": 2, "66": 1}
    assert result[1]["preceding_rng_window"][-1]["result"] == 8
    assert result[1]["following_rng_window"][0]["result"] == 9


def test_duplicate_same_caller_and_result_is_rejected_as_ambiguous():
    records = _rng_records()
    records.append(
        {
            "kind": "rng_core",
            "seq": 5,
            "thread_slot": 0,
            "caller_id": 60,
            "result": 4,
        }
    )

    with pytest.raises(SpawnCoordinateRngError, match="ambiguous"):
        match_spawn_coordinate_rng_records(
            records, [_events()[1]], return_map=_return_map()
        )


def test_return_map_drift_is_rejected_before_joining():
    return_map = _return_map()
    return_map["callers"][59]["call_rva"] = "0x00000000"

    with pytest.raises(SpawnCoordinateRngError, match="pinned seam"):
        match_spawn_coordinate_rng_records(
            _rng_records(), _events(), return_map=return_map
        )


def _analysis(capture_id: str, ordinal: int, caller_21: int) -> dict:
    return {
        "schema_version": 1,
        "kind": "spawn_coordinate_rng_attribution",
        "capture_id": capture_id,
        "status": "attributed",
        "events": [
            {
                "kind": "selector_standard_draw",
                "caller_id": 60,
                "raw_rng": ordinal * 3,
                "rng_ordinal": ordinal,
                "upstream_caller_counts": {"21": caller_21, "59": 0},
            }
        ],
    }


def test_comparison_reports_variable_ordinal_and_upstream_caller():
    comparison = compare_spawn_coordinate_rng_attributions(
        [_analysis("one", 10, 2), _analysis("two", 13, 5)]
    )

    assert comparison["ordinal_stable"] is False
    assert comparison["selector_caller_ids"] == [60, 60]
    assert comparison["varying_upstream_callers"] == [
        {"caller_id": 21, "counts": [2, 5], "minimum": 2, "maximum": 5, "spread": 3}
    ]
    assert comparison["classification"].endswith("call_order_variable")


def test_comparison_rejects_more_than_one_selector_event():
    analysis = _analysis("one", 10, 2)
    analysis["events"].append(deepcopy(analysis["events"][0]))
    with pytest.raises(SpawnCoordinateRngError, match="exactly one"):
        compare_spawn_coordinate_rng_attributions([analysis])


def test_role_overlay_accounts_for_ordinal_delta_by_domain(monkeypatch):
    analyses = [_analysis("one", 10, 2), _analysis("two", 13, 5)]
    analyses[0]["events"][0]["upstream_caller_counts"]["4"] = 7
    analyses[1]["events"][0]["upstream_caller_counts"]["4"] = 7
    overlay = {
        "caller_roles": [
            {
                "caller_id": 4,
                "role_id": "particle_presentation",
                "domain": "presentation",
            }
        ]
    }
    monkeypatch.setattr(
        "src.observatory.spawn_coordinate_rng.validate_rng_caller_role_map_binding",
        lambda value, return_map: {"artifact_sha256": "a" * 64},
    )

    explanation = explain_spawn_coordinate_rng_variation(
        analyses,
        caller_role_overlay=overlay,
        return_map={},
    )

    assert explanation["ordinal_deltas_from_first"] == [0, 3]
    assert explanation["classified_count_deltas_from_first"] == [0, 3]
    assert explanation["ordinal_deltas_fully_accounted"] is True
    assert explanation["unclassified_varying_caller_ids"] == []
    assert explanation["role_counts"] == [
        {
            "role_id": "lua_random_int_boundary",
            "domain": "shared_lua_boundary",
            "caller_ids": [21],
            "counts": [2, 5],
            "minimum": 2,
            "maximum": 5,
            "spread": 3,
        }
    ]
