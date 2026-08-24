from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.event_frame_visibility import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    EventFrameVisibilityError,
    validate_event_frame_visibility_map,
    validate_event_frame_visibility_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
VISIBILITY_MAP = ROOT / "data" / "observatory" / "native" / (
    "windows_build_13725832_31fe35265598_event_frame_visibility.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(VISIBILITY_MAP.read_text(encoding="utf-8"))


def test_committed_map_proves_next_update_visibility_without_overclaim():
    value = _load()
    result = validate_event_frame_visibility_map_binding(value)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["status"] == "bound"
    assert result["active_boardplayer_dispatch_chain_proven"] is True
    assert result["board_effect_update_before_base_update_proven"] is True
    assert result["sole_direct_event_publisher_call_proven"] is True
    assert result["exact_event_frame_visibility_proven"] is True
    assert result["same_outer_update_visibility"] is False
    assert result["next_ordinary_outer_update_visibility"] is True
    assert result["simulator_change_required"] is False
    assert value["identity"]["executable_sha256"] == EXPECTED_EXECUTABLE_SHA256
    assert value["summary"] == {
        "active_boardplayer_dispatch_chain_proven": True,
        "board_effect_update_before_base_update_proven": True,
        "control_window_count": 16,
        "data_pointer_count": 2,
        "dependency_count": 2,
        "direct_edge_count": 9,
        "exact_event_frame_visibility_proven": True,
        "finding_count": 6,
        "next_ordinary_outer_update_visibility": True,
        "region_count": 13,
        "same_outer_update_visibility": False,
        "simulator_change_required": False,
        "sole_direct_event_publisher_call_proven": True,
        "source_count": 1,
        "string_anchor_count": 1,
        "unresolved_count": 4,
    }

    buffers = value["contracts"]["event_buffers"]
    assert buffers["recorder_destination"] == "pending"
    assert buffers["publisher_destination"] == "readable"
    assert buffers["get_event_count_source"] == "readable"
    assert buffers["event_publisher_direct_call_sites"] == ["0x000e55ac"]

    dispatch = value["contracts"]["dispatch_chain"]
    assert dispatch["outer_game_construction_store_proven"] is True
    assert dispatch["outer_game_vtable_slot"] == "+0x04"
    assert dispatch["game_vtable_slot_target_rva"] == "0x00208c40"
    assert dispatch["battle_boardplayer_offset"] == "+0xc204"
    assert dispatch["boardplayer_update_vtable_slot"] == "+0x10"
    assert dispatch["boardplayer_vtable_slot_target_rva"] == "0x0018ae90"

    timing = value["contracts"]["board_death_visibility"]
    assert timing["event_recorded_during"] == "Board/effect update"
    assert timing["same_outer_update_base_update_reads_new_event"] is False
    assert timing["next_ordinary_outer_update_publishes_new_event"] is True
    assert timing["next_ordinary_outer_update_base_update_can_read_new_event"] is True
    assert timing["visibility_delay_outer_updates"] == 1
    assert timing["multiple_same_pass_deaths_publish_as_one_readable_batch"] is True

    scope = value["contracts"]["scope"]
    assert scope["events_recorded_elsewhere_in_outer_update_generalized"] is False
    assert scope["wall_clock_frame_duration_claimed"] is False
    assert scope["non_windows_equivalence_claimed"] is False
    assert {item["id"] for item in value["unresolved"]} == {
        "non_board_event_producers",
        "cached_controller_type",
        "terminal_transition_delivery",
        "non_windows_equivalence",
    }


def test_binding_rejects_timing_dispatch_or_scope_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["contracts"]["board_death_visibility"][
        "same_outer_update_base_update_reads_new_event"
    ] = True
    with pytest.raises(EventFrameVisibilityError, match="fields differ"):
        validate_event_frame_visibility_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["dispatch_chain"]["boardplayer_update_vtable_slot"] = "+0x14"
    with pytest.raises(EventFrameVisibilityError, match="fields differ"):
        validate_event_frame_visibility_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["contracts"]["scope"][
        "events_recorded_elsewhere_in_outer_update_generalized"
    ] = True
    with pytest.raises(EventFrameVisibilityError, match="fields differ"):
        validate_event_frame_visibility_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["solver_impact"]["simulator_change_required"] = True
    with pytest.raises(EventFrameVisibilityError, match="fields differ"):
        validate_event_frame_visibility_map_binding(altered)


def test_exact_local_executable_source_and_dependencies_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_event_frame_visibility_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["exact_event_frame_visibility_proven"] is True
    assert result["same_outer_update_visibility"] is False
    assert result["next_ordinary_outer_update_visibility"] is True
    assert result["simulator_change_required"] is False
