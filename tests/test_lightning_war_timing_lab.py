from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lightning_war_timing_lab.py"
SPEC = importlib.util.spec_from_file_location("lightning_war_timing_lab", SCRIPT)
lab = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = lab
SPEC.loader.exec_module(lab)


def test_stamp_lightning_war_timing_session_sets_solver_target(tmp_path):
    session_path = tmp_path / "active_session.json"

    result = lab._stamp_lightning_war_timing_session(session_path)
    saved = json.loads(session_path.read_text(encoding="utf-8"))

    assert result["status"] == "OK"
    assert saved["squad"] == "Blitzkrieg"
    assert saved["achievement_targets"] == ["Lightning War"]
    assert saved["difficulty"] == 0
    assert "lightning_war_timing_lab" in saved["tags"]


def test_profile_boundary_from_report_keeps_first_milestone_evidence():
    report = {
        "status": "PASS",
        "branch_label": "archive_intro.default",
        "run_id": "lightning_ui_timing_test",
        "report_path": "run_notes/lightning_ui_timing_loop/report.json",
        "marks": {"archive_click": 7.0, "intro_continue": 9.5},
        "in_game_timers": {
            "red_map_detected": {
                "status": "OK",
                "label": "red_map_detected",
                "clock_source": "memory_visible_timer_context",
                "source": "visible_timer_string",
                "game_timer": "0:00:06",
                "game_seconds": 6.0,
                "timer_validation": "range_checked_lightning_limit",
                "fallback_save_timer": {
                    "status": "OK",
                    "clock_source": "save_current_time",
                    "source": "profile_current_time",
                    "game_timer": "0:00:06",
                    "game_seconds": 6.12,
                    "game_timer_ms": 6120.0,
                },
            }
        },
        "frame_delta_report": {"contact_sheet_path": "contact.png"},
        "red_detection": {
            "detected_at_seconds": 10.25,
            "region_count": 5,
            "screenshot_path": "red.png",
            "selected_region": {
                "index": 2,
                "window_x": 620,
                "window_y": 300,
                "area_window": 1200.0,
                "coordinate_space": "physical_window",
            },
        },
    }

    boundary = lab._profile_boundary_from_report(report)

    assert boundary["status"] == "PASS"
    assert boundary["timer_zero"] == "lower difficulty setup Start click"
    assert (
        boundary["primary_time_source"]
        == "validated_memory_live_numeric_candidate_when_available"
    )
    assert boundary["fallback_time_source"] == "save_profile_current_time_not_top_right_validated"
    assert boundary["archive_click_wall_seconds"] == 7.0
    assert boundary["red_map_detected_wall_seconds"] == 10.25
    assert boundary["red_map_detected_game_seconds"] is None
    assert boundary["red_map_detected_game_timer"] is None
    assert boundary["in_game_timer"]["red_map_detected"]["game_timer"] == "0:00:06"
    assert (
        boundary["in_game_timer"]["red_map_detected"]["fallback_save_timer"]["game_seconds"]
        == 6.12
    )
    assert boundary["region_count"] == 5
    assert boundary["chosen_probe_region"]["window_x"] == 620
    assert boundary["evidence"]["contact_sheet_path"] == "contact.png"


def test_profile_boundary_prefers_red_detection_frame_clock():
    report = {
        "status": "PASS",
        "branch_label": "archive_intro.default",
        "run_id": "lightning_ui_timing_test",
        "report_path": "run_notes/lightning_ui_timing_loop/report.json",
        "marks": {"archive_click": 7.0, "intro_continue": 9.5},
        "in_game_timers": {
            "red_map_detected": {
                "status": "OK",
                "label": "red_map_detected_screenshot_pair",
                "clock_source": "memory_live_numeric_candidate",
                "source": "validated_live_numeric_cycle",
                "game_timer": "0:00:06",
                "game_seconds": 6.0,
                "timer_validation": "validated_live_numeric_cycle",
            }
        },
        "frame_delta_report": {"contact_sheet_path": "contact.png"},
        "red_detection": {
            "detected_at_seconds": 10.25,
            "region_count": 2,
            "screenshot_path": "red.png",
            "detected_frame_timer": {
                "status": "OK",
                "label": "red_map_detected_frame",
                "clock_source": "memory_live_numeric_candidate",
                "source": "screenshot_frame_clock",
                "game_timer": "0:00:05",
                "game_seconds": 5.25,
                "timer_validation": "validated_live_numeric_cycle",
            },
            "selected_region": {
                "index": 0,
                "window_x": 620,
                "window_y": 300,
            },
        },
    }

    boundary = lab._profile_boundary_from_report(report)

    assert boundary["red_map_detected_game_seconds"] == 5.25
    assert boundary["red_map_detected_game_timer"] == "0:00:05"
    assert boundary["in_game_timer"]["red_map_detected"]["source"] == "screenshot_frame_clock"
    assert (
        boundary["in_game_timer"]["red_map_detected_paired_after_detection"][
            "game_seconds"
        ]
        == 6.0
    )


def test_wait_for_archive_red_map_returns_pass_on_first_region(monkeypatch):
    events = []
    visible_calls = {"count": 0}
    frames = [
        {
            "screenshot_path": "map.png",
            "timer_seconds": 1.0,
        }
    ]

    class FakeScreenshots:
        def capture_once(self, *, clock_state, note):
            assert clock_state == "opening_probe"
            assert note == "red_map_probe"
            return frames.pop(0)

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))

    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=True: visible_calls.update(count=visible_calls["count"] + 1)
        or {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(lab.fast, "visible_route_dialogue", lambda visible: False)
    monkeypatch.setattr(
        lab.fast,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "region_count": 1,
            "regions": [{"index": 1, "window_x": 500, "window_y": 300}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "select_red_region_candidate",
        lambda regions: (regions["regions"][0], {"candidate_order": regions["regions"]}),
    )
    monkeypatch.setattr(lab, "_elapsed", lambda start: 1.0)
    monkeypatch.setattr(
        lab,
        "read_in_game_timer",
        lambda profile, *, label, use_memory, timer_address=None, live_timer_address=None, live_timer_kind=None: {
            "status": "OK",
            "clock_source": "memory_timeline_playtime_address",
            "game_timer": "0:00:06",
            "game_seconds": 6.0,
            "timer_validation": "calibrated_pause_menu_timeline_playtime_address",
        },
    )

    result = lab.wait_for_archive_red_map(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=0x138A5900,
        memory_live_timer_address=None,
        memory_live_timer_kind=None,
        max_seconds=2.0,
        interval_seconds=0.01,
    )

    assert result["status"] == "PASS"
    assert result["region_count"] == 1
    assert result["selected_region"]["window_x"] == 500
    assert result["paired_in_game_timer"]["game_timer"] == "0:00:06"
    assert result["detected_frame_timer"]["status"] == "UNKNOWN"
    assert visible_calls["count"] == 0
    assert any(event_type == "opening_red_region_probe" for event_type, _ in events)


def test_wait_for_archive_red_map_carries_frame_clock(monkeypatch):
    frames = [
        {
            "screenshot_path": "map.png",
            "timer_seconds": 1.0,
            "frame_clock_status": "OK",
            "frame_clock": {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:05",
                "game_seconds": 5.25,
                "pid": 123,
                "address": "0x00000000122e5dbc",
                "raw": 5.25,
                "timer_validation": "validated_live_numeric_cycle",
            },
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:05",
            "game_seconds": 5.25,
        }
    ]

    class FakeScreenshots:
        def capture_once(self, *, clock_state, note):
            assert clock_state == "opening_probe"
            assert note == "red_map_probe"
            return frames.pop(0)

    class FakeTelemetry:
        def event(self, event_type, **payload):
            return payload

    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=True: {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(lab.fast, "visible_route_dialogue", lambda visible: False)
    monkeypatch.setattr(
        lab.fast,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "region_count": 1,
            "regions": [{"index": 1, "window_x": 500, "window_y": 300}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "select_red_region_candidate",
        lambda regions: (regions["regions"][0], {"candidate_order": regions["regions"]}),
    )
    monkeypatch.setattr(lab, "_elapsed", lambda start: 1.0)
    monkeypatch.setattr(
        lab,
        "read_in_game_timer",
        lambda profile, *, label, use_memory, timer_address=None, live_timer_address=None, live_timer_kind=None: {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:06",
            "game_seconds": 6.0,
            "timer_validation": "validated_live_numeric_cycle",
        },
    )

    result = lab.wait_for_archive_red_map(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        max_seconds=2.0,
        interval_seconds=0.01,
    )

    assert result["detected_frame_timer"]["source"] == "screenshot_frame_clock"
    assert result["detected_frame_timer"]["game_seconds"] == 5.25
    assert result["detected_frame_timer"]["clock_source"] == "memory_live_numeric_candidate"
    assert result["paired_in_game_timer"]["game_seconds"] == 6.0


def test_click_selected_red_mission_preview_clicks_captures_and_pauses(monkeypatch):
    events = []
    clicks = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def capture_once(self, *, clock_state, note):
            assert clock_state == "mission_preview_probe"
            assert note == "after_red_mission_click"
            return {
                "screenshot_path": "preview.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:07",
                    "game_seconds": 7.0,
                    "pid": 123,
                    "address": "0x00000000122e5dbc",
                    "raw": 7.0,
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:07",
                "game_seconds": 7.0,
            }

    def fake_click(name, x, y, *, hover_seconds, settle_seconds, hold_seconds):
        clicks.append(
            {
                "name": name,
                "x": x,
                "y": y,
                "hover_seconds": hover_seconds,
                "settle_seconds": settle_seconds,
                "hold_seconds": hold_seconds,
            }
        )
        return {"status": "OK", "window_x": x, "window_y": y}

    monkeypatch.setattr(lab.fast, "click_hovered_point", fake_click)
    monkeypatch.setattr(lab, "_elapsed", lambda start: 10.0 + len(events))
    monkeypatch.setattr(
        lab,
        "read_in_game_timer",
        lambda profile, *, label, use_memory, timer_address=None, live_timer_address=None, live_timer_kind=None: {
            "status": "OK",
            "label": label,
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:07",
            "game_seconds": 7.0,
            "timer_validation": "validated_live_numeric_cycle",
        },
    )

    result = lab.click_selected_red_mission_preview(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        red_detection={
            "status": "PASS",
            "selected_region": {"index": 0, "window_x": 1062, "window_y": 694},
        },
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        hover_seconds=0.05,
        settle_seconds=0.25,
        hold_seconds=0.12,
        pause_after_click=True,
    )

    assert result["status"] == "OK"
    assert clicks[0]["name"] == "red_mission_region"
    assert clicks[0]["x"] == 1062
    assert clicks[0]["y"] == 694
    assert clicks[1]["name"] == "pause"
    assert clicks[1]["x"] == 38
    assert clicks[1]["y"] == 28
    assert result["preview_frame_timer"]["source"] == "screenshot_frame_clock"
    assert result["preview_frame_timer"]["game_seconds"] == 7.0
    assert [event_type for event_type, _payload in events] == [
        "red_mission_region_click",
        "mission_preview_probe",
        "mission_preview_pause",
    ]


def test_click_start_mission_from_preview_clicks_highlighted_thumbnail(monkeypatch):
    events = []
    clicks = []
    visible_calls = {"count": 0}

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:09",
                    "game_seconds": 9.0,
                    "pid": 123,
                    "address": "0x00000000122e5dbc",
                    "raw": 9.0,
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:09",
                "game_seconds": 9.0,
            }

    screenshots = FakeScreenshots()

    def fake_visible(include_ocr=False):
        visible_calls["count"] += 1
        if visible_calls["count"] < 2:
            return {"status": "OK", "visible_ui": "mission_preview_panel"}
        return {"status": "OK", "visible_ui": "deployment_screen"}

    def fake_click_ui(control, *, settle_seconds=0.05, hold_seconds=None):
        clicks.append(
            {
                "kind": "ui",
                "control": control,
                "settle_seconds": settle_seconds,
                "hold_seconds": hold_seconds,
            }
        )
        return {"status": "OK", "control": control}

    def fake_click_hovered(name, x, y, *, hover_seconds, settle_seconds, hold_seconds):
        clicks.append(
            {
                "kind": "hover",
                "name": name,
                "x": x,
                "y": y,
                "hover_seconds": hover_seconds,
                "settle_seconds": settle_seconds,
                "hold_seconds": hold_seconds,
            }
        )
        return {"status": "OK", "window_x": x, "window_y": y}

    monkeypatch.setattr(lab.fast, "_lightning_visible_ui_snapshot", fake_visible)
    monkeypatch.setattr(lab.fast, "visible_route_dialogue", lambda visible: visible_calls["count"] == 1)
    monkeypatch.setattr(
        lab.fast,
        "visible_startable_mission_preview",
        lambda visible: visible.get("visible_ui") == "mission_preview_panel",
    )
    monkeypatch.setattr(lab.fast, "visible_text_lower", lambda visible: "")
    monkeypatch.setattr(lab.fast, "visible_deployment_screen", lambda visible: visible.get("visible_ui") == "deployment_screen")
    monkeypatch.setattr(
        lab.fast,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "in_active_mission": True,
            "mission_id": "Mission_Volatile",
            "deployment_zone_count": 14,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    )
    monkeypatch.setattr(lab.fast, "deployment_snapshot_ready", lambda snapshot: True)
    monkeypatch.setattr(lab.fast, "compact_visible_ui", lambda visible: visible)
    monkeypatch.setattr(lab.fast, "click_ui_control", fake_click_ui)
    monkeypatch.setattr(lab.fast, "click_hovered_point", fake_click_hovered)
    monkeypatch.setattr(lab.sys, "platform", "win32")
    monkeypatch.setattr(lab.fast, "_lightning_ensure_pause_state", lambda *, reason: {"status": "OK", "reason": reason})
    monkeypatch.setattr(lab, "_elapsed", lambda start: 20.0 + len(events))
    monkeypatch.setattr(
        lab,
        "read_in_game_timer",
        lambda profile, *, label, use_memory, timer_address=None, live_timer_address=None, live_timer_kind=None: {
            "status": "OK",
            "label": label,
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:09",
            "game_seconds": 9.0,
            "timer_validation": "validated_live_numeric_cycle",
        },
    )

    result = lab.click_start_mission_from_preview(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=screenshots,
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        settle_seconds=0.25,
        hover_seconds=0.05,
        hold_seconds=0.12,
        max_seconds=2.0,
        interval_seconds=0.01,
        pause_after_click=True,
        pre_start_visible_probe=False,
        deployment_trigger_source="visible_ui",
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "deployment_visible"
    assert result["dialogue_observation"]["route_dialogue_visible"] is None
    assert result["dialogue_observation"]["pre_start_visible_probe"] == "skipped_after_proven_hover_target"
    assert clicks[0]["name"] == "mission_preview_board"
    assert clicks[0]["hover_seconds"] == 0.05
    assert result["pause"]["reason"] == "timing_lab_start_mission_deployment_probe"
    assert screenshots.calls == [("deployment_probe", "after_start_mission_click")]
    assert [event_type for event_type, _payload in events] == [
        "mission_preview_pre_start_probe_skipped",
        "mission_preview_startable_probe",
        "start_mission_click",
        "deployment_probe",
        "deployment_pause",
    ]
    assert visible_calls["count"] == 2
    assert events[3][1]["bridge_deployment_ready"] is True
    assert events[3][1]["deployment_visible"] is True
    assert result["first_bridge_deployment_sample"]["bridge_deployment_ready"] is True


def test_click_start_mission_can_trigger_on_screenshot_yellow(monkeypatch):
    events = []
    clicks = []
    yellow_calls = {"count": 0}
    live_snapshot_calls = {"count": 0}

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}_{len(self.calls)}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:14",
                    "game_seconds": 14.0,
                    "pid": 123,
                    "address": "0x00000000122e5dbc",
                    "raw": 14.0,
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:14",
                "game_seconds": 14.0,
            }

    def fake_yellow(frame):
        yellow_calls["count"] += 1
        if yellow_calls["count"] < 2:
            return {
                "status": "OK",
                "yellow": 300,
                "threshold": 5000,
                "deployment_visible": False,
            }
        return {
            "status": "OK",
            "yellow": 6500,
            "threshold": 5000,
            "deployment_visible": True,
        }

    def fake_live_snapshot():
        live_snapshot_calls["count"] += 1
        return {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "in_active_mission": True,
            "mission_id": "Mission_Volatile",
            "deployment_zone_count": 14,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    def fake_click_hovered(name, x, y, *, hover_seconds, settle_seconds, hold_seconds):
        clicks.append({"name": name, "x": x, "y": y})
        return {"status": "OK", "window_x": x, "window_y": y}

    visible_calls = {"count": 0}

    def fake_startable_visible(include_ocr=False):
        visible_calls["count"] += 1
        return {"status": "OK", "visible_ui": "mission_preview_panel"}

    monkeypatch.setattr(lab.fast, "_lightning_visible_ui_snapshot", fake_startable_visible)
    monkeypatch.setattr(
        lab.fast,
        "visible_startable_mission_preview",
        lambda visible: visible.get("visible_ui") == "mission_preview_panel",
    )
    monkeypatch.setattr(lab.fast, "visible_text_lower", lambda visible: "")
    monkeypatch.setattr(lab, "_deployment_yellow_signal_from_frame", fake_yellow)
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_live_snapshot)
    monkeypatch.setattr(lab.fast, "deployment_snapshot_ready", lambda snapshot: bool(snapshot))
    monkeypatch.setattr(lab.fast, "click_hovered_point", fake_click_hovered)
    monkeypatch.setattr(lab.sys, "platform", "win32")
    monkeypatch.setattr(lab.fast, "_lightning_ensure_pause_state", lambda *, reason: {"status": "OK", "reason": reason})
    monkeypatch.setattr(lab, "_elapsed", lambda start: 40.0 + len(events))
    monkeypatch.setattr(
        lab,
        "read_in_game_timer",
        lambda profile, *, label, use_memory, timer_address=None, live_timer_address=None, live_timer_kind=None: {
            "status": "OK",
            "label": label,
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:14",
            "game_seconds": 14.0,
            "timer_validation": "validated_live_numeric_cycle",
        },
    )

    result = lab.click_start_mission_from_preview(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        settle_seconds=0.25,
        hover_seconds=0.05,
        hold_seconds=0.12,
        max_seconds=2.0,
        interval_seconds=0.01,
        pause_after_click=True,
        pre_start_visible_probe=False,
        deployment_trigger_source="screenshot_yellow",
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "deployment_yellow_screenshot"
    assert visible_calls["count"] == 1
    assert yellow_calls["count"] == 2
    assert live_snapshot_calls["count"] == 0
    assert events[3][1]["deployment_yellow_signal"]["yellow"] == 300
    assert events[3][1]["visible_ui"] is None
    assert events[4][1]["deployment_yellow_signal"]["yellow"] == 6500
    assert result["first_bridge_deployment_sample"] is None


def test_click_start_mission_refuses_non_startable_preview(monkeypatch):
    events = []
    clicks = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def capture_once(self, *, clock_state, note):
            raise AssertionError("deployment screenshots should not run")

    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: {
            "status": "OK",
            "visible_ui": "island_map",
            "ocr_text": "The Pasture No Vek Detected",
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "visible_startable_mission_preview",
        lambda visible: False,
    )
    monkeypatch.setattr(
        lab.fast,
        "visible_text_lower",
        lambda visible: str(visible.get("ocr_text") or "").lower(),
    )
    monkeypatch.setattr(lab.fast, "compact_visible_ui", lambda visible: visible)
    monkeypatch.setattr(lab.fast, "click_hovered_point", lambda *a, **k: clicks.append((a, k)))
    monkeypatch.setattr(lab, "_elapsed", lambda start: 12.0 + len(events))

    result = lab.click_start_mission_from_preview(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        settle_seconds=0.25,
        hover_seconds=0.05,
        hold_seconds=0.12,
        max_seconds=2.0,
        interval_seconds=0.01,
        pause_after_click=True,
        pre_start_visible_probe=False,
        deployment_trigger_source="screenshot_yellow",
    )

    assert result["status"] == "FAIL"
    assert result["reason"] == "mission_preview_not_startable"
    assert clicks == []
    assert [event_type for event_type, _payload in events] == [
        "mission_preview_pre_start_probe_skipped",
        "mission_preview_startable_probe",
    ]


def test_fast_followup_region_click_requires_startable_preview(monkeypatch):
    probes = [
        {"index": 0, "window_x": 100, "window_y": 200},
        {"index": 1, "window_x": 300, "window_y": 400},
    ]
    clicked = []

    def fake_click_stable(*, tried_keys=None):
        clicked.append(set(tried_keys or set()))
        return probes[len(clicked) - 1]

    visible_results = [
        {"status": "OK", "visible_ui": "island_map", "ocr_text": "No Vek Detected"},
        {
            "status": "OK",
            "visible_ui": "mission_preview_panel",
            "ocr_text": "Bonus Objectives Start Mission",
        },
    ]

    monkeypatch.setattr(
        lab.fast,
        "click_stable_red_mission_after_result",
        fake_click_stable,
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: visible_results[len(clicked) - 1],
    )
    monkeypatch.setattr(
        lab.fast,
        "visible_startable_mission_preview",
        lambda visible: visible.get("visible_ui") == "mission_preview_panel",
    )
    monkeypatch.setattr(lab.fast, "compact_visible_ui", lambda visible: visible)
    monkeypatch.setattr(lab.fast.time, "sleep", lambda _seconds: None)

    result = lab.fast.click_startable_red_mission_after_result(max_attempts=2)

    assert result["status"] == "MISSION_PREVIEW_OPENED"
    assert result["red_region"]["index"] == 1
    assert clicked == [set(), {"index:0"}]
    assert result["attempts"][0]["startable_preview_visible"] is False
    assert result["attempts"][1]["startable_preview_visible"] is True


def test_deploy_recommended_after_visible_deployment_runs_helper_and_pauses(monkeypatch):
    events = []
    deploy_calls = []
    timer_labels = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def capture_once(self, *, clock_state, note):
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:13",
                    "game_seconds": 13.0,
                    "pid": 123,
                    "address": "0x00000000122e5dbc",
                    "raw": 13.0,
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:13",
                "game_seconds": 13.0,
            }

    def fake_deploy(*, profile, ui_fallback, verify_after):
        deploy_calls.append(
            {
                "profile": profile,
                "ui_fallback": ui_fallback,
                "verify_after": verify_after,
            }
        )
        return {
            "status": "OK",
            "phase": "combat_player",
            "deployments": [
                {"uid": 1, "visual": "A1"},
                {"uid": 2, "visual": "A2"},
                {"uid": 3, "visual": "A3"},
            ],
        }

    monkeypatch.setattr(lab.fast, "cmd_deploy_recommended", fake_deploy)
    monkeypatch.setattr(
        lab.fast,
        "_lightning_ensure_pause_state",
        lambda *, reason: {"status": "OK", "reason": reason},
    )
    monkeypatch.setattr(lab, "_elapsed", lambda start: 30.0 + len(events))

    def fake_timer(
        profile,
        *,
        label,
        use_memory,
        timer_address=None,
        live_timer_address=None,
        live_timer_kind=None,
    ):
        timer_labels.append(label)
        return {
            "status": "OK",
            "label": label,
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:13",
            "game_seconds": 13.0,
            "timer_validation": "validated_live_numeric_cycle",
        }

    monkeypatch.setattr(lab, "read_in_game_timer", fake_timer)
    monkeypatch.setattr(
        lab,
        "_wait_for_deployment_bridge_ready",
        lambda **kwargs: {
            "status": "OK",
            "ready_sample": {"ready": True},
            "samples": [{"ready": True}],
            "elapsed_seconds": 0.05,
        },
    )

    result = lab.deploy_recommended_after_visible_deployment(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        profile="Alpha",
        use_memory_timer=True,
        memory_timer_address=None,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        pause_after_deploy=True,
        trigger_frame_timer={
            "status": "OK",
            "label": "deployment_probe_frame",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:13",
            "game_seconds": 13.0,
        },
    )

    assert result["status"] == "PASS"
    assert deploy_calls == [
        {"profile": "Alpha", "ui_fallback": False, "verify_after": False}
    ]
    assert result["deploy_result_compact"]["deployment_count"] == 3
    assert result["before_in_game_timer"]["label"] == "deploy_recommended_trigger_frame"
    assert result["bridge_ready_wait"]["status"] == "OK"
    assert result["post_deploy_frame_timer"]["source"] == "screenshot_frame_clock"
    assert result["pause"]["reason"] == "timing_lab_after_deploy_recommended"
    assert timer_labels == [
        "deploy_recommended_after",
        "deploy_recommended_after_pause",
    ]
    assert [event_type for event_type, _payload in events] == [
        "deploy_recommended_start",
        "deploy_recommended_result",
        "post_deploy_probe",
        "deploy_recommended_pause",
    ]


def test_wait_for_deployment_bridge_ready_polls_until_ready(monkeypatch):
    events = []
    snapshots = [
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "in_active_mission": True,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": None,
        },
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "in_active_mission": True,
            "deployment_zone_count": 6,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": None,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", lambda: snapshots.pop(0))
    monkeypatch.setattr(lab.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(lab, "_elapsed", lambda start: float(len(events)))

    result = lab._wait_for_deployment_bridge_ready(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        max_seconds=1.0,
        interval_seconds=0.01,
    )

    assert result["status"] == "OK"
    assert len(result["samples"]) == 2
    assert result["ready_sample"]["snapshot"]["deployment_zone_count"] == 6
    assert [event_type for event_type, _payload in events] == [
        "deployment_bridge_ready_wait",
        "deployment_bridge_ready_wait",
    ]


def test_confirm_deployment_observes_bridge_player_turn_and_pauses(monkeypatch):
    events = []
    clicks = []
    key_presses = []
    clock_samples = [
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:12",
            "game_seconds": 12.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:13",
            "game_seconds": 13.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:19",
            "game_seconds": 19.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:19",
            "game_seconds": 19.5,
        },
    ]
    snapshots = [
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 10,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 1,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            if clock_samples:
                return clock_samples.pop(0)
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:20",
                "game_seconds": 20.0,
            }

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}_{len(self.calls)}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:18",
                    "game_seconds": 18.0 + len(self.calls),
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:18",
                "game_seconds": 18.0 + len(self.calls),
            }

    def fake_snapshot():
        if snapshots:
            return snapshots.pop(0)
        return {
            "status": "OK",
            "phase": "combat_player",
            "turn": 1,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.05: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_snapshot)
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.confirm_deployment_and_observe_opening_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        observe_seconds=1.0,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=1,
        pause_after_ready=True,
    )

    assert result["status"] == "PASS"
    assert result["confirm_signal_source"] == "deploy_recommended_result"
    assert result["player_turn_signal_source"] == "bridge_lua_live_snapshot"
    assert clicks == [("deploy_confirm", 0.05)]
    assert key_presses == [
        ("esc", "pause after opening player turn", "Into the Breach", 0.05)
    ]
    assert result["first_confirm_live_bridge"]["snapshot"]["phase"] == "combat_enemy"
    assert result["first_player_ready_bridge"]["snapshot"]["phase"] == "combat_player"
    assert result["first_player_ready_frame_after_bridge"] is not None
    assert result["before_in_game_timer"]["label"] == "deploy_confirm_click_before"
    assert [event_type for event_type, _payload in events][:3] == [
        "deploy_confirm_signal",
        "deploy_confirm_click",
        "post_confirm_frame",
    ]


def test_solve_execute_end_turn_observes_next_player_turn(monkeypatch):
    events = []
    clicks = []
    key_presses = []
    auto_calls = []
    clock_samples = [
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:28",
            "game_seconds": 28.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:29",
            "game_seconds": 29.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:29",
            "game_seconds": 29.5,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:30",
            "game_seconds": 30.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:40",
            "game_seconds": 40.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:40",
            "game_seconds": 40.5,
        },
    ]
    snapshots = [
        {
            "status": "ERROR",
            "error": "transient_bridge_read",
        },
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 1,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            if clock_samples:
                return clock_samples.pop(0)
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:41",
                "game_seconds": 41.0,
            }

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}_{len(self.calls)}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:40",
                    "game_seconds": 40.0 + len(self.calls),
                    "timer_validation": "validated_live_numeric_cycle",
                },
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:40",
                "game_seconds": 40.0 + len(self.calls),
            }

    def fake_auto_turn(**kwargs):
        auto_calls.append(kwargs)
        return {
            "status": "PLAN",
            "turn": 1,
            "actions_completed": 3,
            "score": 1234,
            "re_solves": 0,
            "wait_entry_seconds": 0.0,
            "batch": [{"type": "left_click", "window_x": 126, "window_y": 120}],
        }

    def fake_snapshot():
        if snapshots:
            return snapshots.pop(0)
        return {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    fake_screenshots = FakeScreenshots()
    monkeypatch.setattr(lab.fast, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_snapshot)
    monkeypatch.setattr(
        lab.fast,
        "_lightning_end_turn_retryable",
        lambda observed, turn: False,
    )
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=fake_screenshots,
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=1,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "PASS"
    assert auto_calls == [
        {
            "time_limit": 10.0,
            "max_wait": 8.0,
            "wait_poll_interval": 0.2,
            "resume_before_execute": True,
            "lightning_speed_loss_policy": True,
            "destroy_time_pods": True,
        }
    ]
    assert clicks == [("end_turn", 0.0)]
    assert key_presses == [
        (
            "esc",
            "pause after combat post-end-turn player ready",
            "Into the Breach",
            0.05,
        )
    ]
    assert fake_screenshots.calls[0] == (
        "post_end_turn_observe",
        "after_combat_end_turn",
    )
    assert result["auto_turn_summary"]["actions_completed"] == 3
    assert result["first_non_player_bridge"]["snapshot"]["phase"] == "combat_enemy"
    assert result["bridge_samples"][0]["left_player_turn"] is False
    assert result["bridge_samples"][0]["snapshot"]["status"] == "ERROR"
    assert result["first_player_ready_bridge"]["snapshot"]["phase"] == "combat_player"
    assert result["first_player_ready_frame_after_bridge"] is not None
    assert [event_type for event_type, _payload in events][:3] == [
        "combat_auto_turn_start",
        "combat_auto_turn_result",
        "combat_end_turn_click",
    ]


def test_solve_execute_end_turn_accepts_direct_next_player_turn(monkeypatch):
    clicks = []
    key_presses = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            return {"event_type": event_type, **payload}

    class FakeScreenshots:
        frame_clock_sampler = None

        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:01:23",
                "game_seconds": 83.0,
            }

        def capture_once(self, *, clock_state, note):
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "score": 1234,
            "re_solves": 0,
            "batch": [{"type": "left_click"}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: (_ for _ in ()).throw(
            AssertionError("visible UI probe should not run after bridge-ready")
        ),
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_end_turn_retryable",
        lambda observed, turn: False,
    )
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=0.5,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
        stop_on_region_secured=True,
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "combat_post_end_turn_player_ready"
    assert result["boundary"] == "player_turn_ready"
    assert result["first_non_player_bridge"] is None
    assert result["first_player_ready_bridge"]["snapshot"]["turn"] == 3
    assert clicks == [("end_turn", 0.0)]
    assert key_presses


def test_solve_execute_end_turn_does_not_retry_ambiguous_spent_turn(monkeypatch):
    clicks = []
    key_presses = []
    capture_calls = []
    state = {"after_retry_samples": 0}

    class FakeTelemetry:
        def __init__(self):
            self.events = []

        def event(self, event_type, **payload):
            self.events.append((event_type, payload))
            return {"event_type": event_type, **payload}

    class FakeScreenshots:
        frame_clock_sampler = None

        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:34",
                "game_seconds": 34.0,
            }

        def capture_once(self, *, clock_state, note):
            capture_calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    def fake_snapshot():
        if len(clicks) < 2:
            return {
                "status": "OK",
                "phase": "combat_player",
                "turn": 2,
                "active_mechs": 0,
                "mech_count": 3,
                "deployment_zone_count": 0,
                "bridge_heartbeat_alive": True,
                "bridge_heartbeat_stale": False,
            }
        state["after_retry_samples"] += 1
        if state["after_retry_samples"] == 1:
            return {
                "status": "OK",
                "phase": "combat_enemy",
                "turn": 2,
                "active_mechs": 0,
                "mech_count": 3,
                "deployment_zone_count": 0,
                "bridge_heartbeat_alive": True,
                "bridge_heartbeat_stale": False,
            }
        return {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "score": 1234,
            "re_solves": 0,
            "batch": [{"type": "left_click"}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_snapshot)
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    telemetry = FakeTelemetry()
    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=telemetry,
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.02,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=0.01,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "FAIL"
    assert result["reason"] == "combat_post_end_turn_not_detected"
    assert result["first_non_player_bridge"] is None
    assert result["first_player_ready_bridge"] is None
    assert clicks == [("end_turn", 0.0)]
    assert key_presses == []
    assert result["end_turn_retry_click"] is None
    assert result["end_turn_retry_elapsed_after_end_turn_seconds"] is None
    assert result["end_turn_retry_bridge_sample_count"] is None
    retry_events = [
        payload
        for event_type, payload in telemetry.events
        if event_type == "combat_end_turn_retry_click"
    ]
    assert retry_events == []


def test_solve_execute_end_turn_suppresses_retry_on_visual_transition(monkeypatch):
    clicks = []
    key_presses = []
    state = {"snapshots": 0}

    class FakeTelemetry:
        def __init__(self):
            self.events = []

        def event(self, event_type, **payload):
            self.events.append((event_type, payload))
            return {"event_type": event_type, **payload}

    class FakeScreenshots:
        frame_clock_sampler = None

        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:36",
                "game_seconds": 36.0,
            }

        def capture_once(self, *, clock_state, note):
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    def fake_snapshot():
        state["snapshots"] += 1
        if state["snapshots"] <= 6:
            return {
                "status": "OK",
                "phase": "combat_player",
                "turn": 2,
                "active_mechs": 0,
                "mech_count": 3,
                "deployment_zone_count": 0,
                "bridge_heartbeat_alive": True,
                "bridge_heartbeat_stale": False,
            }
        if state["snapshots"] == 7:
            return {
                "status": "OK",
                "phase": "combat_enemy",
                "turn": 2,
                "active_mechs": 0,
                "mech_count": 3,
                "deployment_zone_count": 0,
                "bridge_heartbeat_alive": True,
                "bridge_heartbeat_stale": False,
            }
        return {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "score": 1234,
            "re_solves": 0,
            "batch": [{"type": "left_click"}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_snapshot)
    monkeypatch.setattr(
        lab,
        "_post_end_turn_transition_banner_from_frame",
        lambda frame: {
            "status": "OK",
            "transition_visible": True,
            "text_bright_fraction": 0.13,
            "text_dark_fraction": 0.74,
            "band_dark_fraction": 0.73,
        },
    )
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.02,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=0.01,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "combat_post_end_turn_player_ready"
    assert clicks == [("end_turn", 0.0)]
    assert result["end_turn_retry_click"] is None
    assert result["first_non_player_visual"]["transition_banner"][
        "transition_visible"
    ] is True
    assert result["first_non_player_bridge"]["snapshot"]["phase"] == "combat_enemy"
    assert result["first_player_ready_bridge"]["snapshot"]["turn"] == 3
    assert key_presses


def test_solve_execute_end_turn_stops_on_auto_turn_block(monkeypatch):
    events = []
    auto_calls = []
    clock_samples = [
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:22",
            "game_seconds": 22.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:34",
            "game_seconds": 34.0,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        frame_clock_sampler = None

        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            if clock_samples:
                return clock_samples.pop(0)
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:34",
                "game_seconds": 34.0,
            }

    def fake_auto_turn(**kwargs):
        auto_calls.append(kwargs)
        return {
            "status": "FUZZY_INVESTIGATE_BLOCKED",
            "turn": 1,
            "actions_completed": 3,
            "score": 139507,
            "re_solves": 2,
            "held_end_turn_batch": [{"type": "left_click"}],
            "block_reason": {
                "reason": "enemy_survived_unexpectedly",
                "signature": "death|Ranged_Rockthrow|attack",
                "weapon": "Ranged_Rockthrow",
            },
            "next_step": "Do not click End Turn.",
        }

    monkeypatch.setattr(lab.fast, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda *args, **kwargs: pytest.fail("End Turn must not be clicked"),
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.2,
        extra_ready_frames=1,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=False,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "FAIL"
    assert result["reason"] == "auto_turn_did_not_return_end_turn_plan"
    assert result["solver_action_signal_source"] == "cmd_auto_turn"
    assert result["end_turn_signal_source"] == "not_clicked_auto_turn_safety_stop"
    assert result["auto_turn_summary"]["status"] == "FUZZY_INVESTIGATE_BLOCKED"
    assert result["safety_stop_reason"]["signature"] == "death|Ranged_Rockthrow|attack"
    assert "death|Ranged_Rockthrow|attack" in lab._combat_next_patch(result)
    assert auto_calls
    assert [event_type for event_type, _payload in events] == [
        "combat_auto_turn_start",
        "combat_auto_turn_result",
    ]


def test_combat_next_patch_calls_out_time_pod_left_alive_block():
    result = {
        "auto_turn_summary": {"status": "SAFETY_BLOCKED"},
        "auto_turn": {
            "status": "SAFETY_BLOCKED",
            "plan_safety": {
                "violations": [
                    {
                        "kind": "pod_unrecovered_final",
                        "blocking": True,
                    }
                ]
            },
        },
    }

    assert lab._auto_turn_time_pod_left_alive_block(result["auto_turn"]) is True
    next_patch = lab._combat_next_patch(result)
    assert "Force a Time Pod destruction line" in next_patch
    assert "do not dirty-consent pod_unrecovered_final" in next_patch


def test_solve_execute_end_turn_reports_time_pod_left_alive_block(monkeypatch):
    events = []
    clicks = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:51",
                "game_seconds": 51.0,
            }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "SAFETY_BLOCKED",
            "turn": 2,
            "score": 122502,
            "dirty_consent_id": "pod-token",
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "violations": [
                    {
                        "kind": "pod_unrecovered_final",
                        "blocking": True,
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda *args, **kwargs: clicks.append(args) or {"status": "OK"},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.2,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "FAIL"
    assert result["reason"] == "time_pod_left_alive_speed_policy_block"
    assert result["end_turn_signal_source"] == (
        "not_clicked_time_pod_left_alive_speed_policy"
    )
    assert result["speed_policy_stop"]["required_resolution"] == (
        "destroy_time_pod_or_reroute"
    )
    assert clicks == []
    assert [event_type for event_type, _payload in events] == [
        "combat_auto_turn_start",
        "combat_auto_turn_result",
    ]


def test_solve_execute_end_turn_auto_consents_safety_block(monkeypatch):
    events = []
    auto_calls = []
    clicks = []
    key_presses = []
    snapshots = [
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 2,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:53",
                "game_seconds": 53.0,
            }

        def capture_once(self, *, clock_state, note):
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    def fake_auto_turn(**kwargs):
        auto_calls.append(kwargs)
        if len(auto_calls) == 1:
            return {
                "status": "SAFETY_BLOCKED",
                "turn": 2,
                "score": 162088,
                "selected_candidate_rank": 0,
                "dirty_consent_id": "dirty-ok",
                "plan_safety": {
                    "status": "DIRTY",
                    "blocking": True,
                    "violations": [
                        {
                            "kind": "mech_on_danger",
                            "blocking": True,
                        }
                    ],
                },
            }
        return {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "score": 162088,
            "re_solves": 0,
            "batch": [{"type": "left_click"}],
        }

    monkeypatch.setattr(lab.fast, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_live_snapshot",
        lambda: snapshots.pop(0) if snapshots else {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_end_turn_retryable",
        lambda observed, turn: False,
    )
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=0.5,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "PASS"
    assert result["auto_turn_safety_block_auto_consent"]["consent"] is True
    assert result["auto_turn_safety_block_auto_consent"]["blocking_kinds"] == [
        "mech_on_danger"
    ]
    assert len(result["auto_turn_attempts"]) == 2
    assert auto_calls[0] == {
        "time_limit": 10.0,
        "max_wait": 8.0,
        "wait_poll_interval": 0.2,
        "resume_before_execute": True,
        "lightning_speed_loss_policy": True,
        "destroy_time_pods": True,
    }
    assert auto_calls[1]["allow_dirty_plan"] is True
    assert auto_calls[1]["candidate_rank"] == 0
    assert auto_calls[1]["dirty_consent_id"] == "dirty-ok"
    assert auto_calls[1]["allow_protected_objective_loss"] is True
    assert auto_calls[1]["allow_objective_loss"] is True
    assert clicks == [("end_turn", 0.0)]
    assert key_presses
    assert "combat_auto_turn_safety_block_auto_consented" in [
        event_type for event_type, _payload in events
    ]


def test_solve_execute_end_turn_skips_qualified_fuzzy_block(monkeypatch):
    events = []
    clicks = []
    key_presses = []
    clock_samples = [
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:22",
            "game_seconds": 22.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:34",
            "game_seconds": 34.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:34",
            "game_seconds": 34.2,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:42",
            "game_seconds": 42.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:50",
            "game_seconds": 50.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:50",
            "game_seconds": 50.3,
        },
    ]
    snapshots = [
        {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 1,
            "active_mechs": 0,
            "mech_count": 3,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            if clock_samples:
                return clock_samples.pop(0)
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:00:51",
                "game_seconds": 51.0,
            }

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}_{len(self.calls)}.png",
                "frame_clock_status": "OK",
                "frame_clock": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "game_timer": "0:00:50",
                    "game_seconds": 50.0,
                    "timer_validation": "validated_live_numeric_cycle",
                },
            }

    def fake_snapshot():
        if snapshots:
            return snapshots.pop(0)
        return {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "FUZZY_INVESTIGATE_BLOCKED",
            "turn": 1,
            "actions_completed": 3,
            "score": 139507,
            "re_solves": 2,
            "held_end_turn_batch": [{"type": "left_click"}],
            "block_reason": {
                "reason": "enemy_survived_unexpectedly",
                "signature": "death|Ranged_Rockthrow|attack",
                "weapon": "Ranged_Rockthrow",
            },
            "next_step": "Do not click End Turn during ordinary play.",
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(lab.fast, "_lightning_live_snapshot", fake_snapshot)
    monkeypatch.setattr(
        lab.fast,
        "_lightning_end_turn_retryable",
        lambda observed, turn: False,
    )
    monkeypatch.setattr(lab.fast, "APP_NAME", "Into the Breach")
    monkeypatch.setattr(
        lab.fast,
        "press_key",
        lambda key, *, description, app_name, settle_seconds=0.05: key_presses.append(
            (key, description, app_name, settle_seconds)
        )
        or {"status": "OK", "key": key},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=1,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "combat_post_end_turn_player_ready_after_fuzzy_block_skip"
    assert result["auto_turn_block_skipped"] is True
    assert result["auto_turn_block_skip_decision"]["signature"] == (
        "death|Ranged_Rockthrow|attack"
    )
    assert result["end_turn_signal_source"] == "fuzzy_block_held_end_turn_speedrun_skip"
    assert result["safety_stop_reason"]["signature"] == "death|Ranged_Rockthrow|attack"
    assert clicks == [("end_turn", 0.0)]
    assert key_presses
    assert "combat_auto_turn_fuzzy_block_skipped" in [
        event_type for event_type, _payload in events
    ]


def test_solve_execute_end_turn_detects_region_secured_and_hovers(monkeypatch):
    events = []
    clicks = []
    hovers = []
    continue_clicks = []
    clock_samples = [
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:52",
            "game_seconds": 52.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:58",
            "game_seconds": 58.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:00:58",
            "game_seconds": 58.1,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:01:04",
            "game_seconds": 64.0,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:01:04",
            "game_seconds": 64.2,
        },
        {
            "status": "OK",
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:01:04",
            "game_seconds": 64.4,
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.calls = []
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            if clock_samples:
                return clock_samples.pop(0)
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:01:05",
                "game_seconds": 65.0,
            }

        def capture_once(self, *, clock_state, note):
            self.calls.append((clock_state, note))
            return {
                "screenshot_path": f"{clock_state}_{len(self.calls)}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    monkeypatch.setattr(
        lab.fast,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "PLAN",
            "turn": 3,
            "actions_completed": 3,
            "score": 100,
            "re_solves": 0,
            "batch": [{"type": "left_click"}],
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_control",
        lambda control, *, settle_seconds=0.0: clicks.append(
            (control, settle_seconds)
        )
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "mission_ending",
            "turn": 3,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "in_active_mission": False,
            "bridge_heartbeat_alive": True,
            "bridge_heartbeat_stale": False,
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: {
            "status": "OK",
            "visible_ui": "island_complete_leave",
            "recommended_control": "leave_island",
            "region_secured_visible": None,
            "screenshot_path": "region.png",
        },
    )
    monkeypatch.setattr(
        lab,
        "list_known_window_controls",
        lambda: {
            "reward_continue": {
                "name": "reward_continue",
                "window_x": 1647,
                "window_y": 985,
            }
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "hover_window_point",
        lambda name, x, y, *, hover_seconds: hovers.append(
            (name, x, y, hover_seconds)
        )
        or {
            "status": "OK",
            "name": name,
            "window_x": x,
            "window_y": y,
            "screen_x": x + 10,
            "screen_y": y + 20,
        },
    )
    monkeypatch.setattr(
        lab.fast,
        "click_ui_control",
        lambda control, *, settle_seconds=0.05, hold_seconds=None: continue_clicks.append(
            (control, settle_seconds, hold_seconds)
        )
        or {"status": "OK", "control": control},
    )

    result = lab.solve_execute_end_turn_and_observe_next_turn(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=1.0,
        screenshot_cadence=0.01,
        bridge_poll_seconds=0.01,
        extra_ready_frames=1,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
        stop_on_region_secured=True,
        visible_poll_seconds=0.01,
        terminal_visual_settle_seconds=0.0,
        hover_region_continue=True,
        region_continue_hover_seconds=0.25,
        click_region_continue=True,
        region_continue_click_settle_seconds=0.35,
    )

    assert result["status"] == "PASS"
    assert result["boundary"] == "region_secured"
    assert result["reason"] == "combat_region_secured_visible"
    assert clicks == [("end_turn", 0.0)]
    assert hovers == [("region_secured_continue", 1647, 985, 0.25)]
    assert continue_clicks == [("reward_continue", 0.35, None)]
    assert result["first_region_secured_visible"]["visible_ui"]["visible_ui"] == (
        "island_complete_leave"
    )
    assert result["region_secured_continue_hover"]["control"]["window_x"] == 1647
    assert result["region_secured_continue_click"]["control"]["window_x"] == 1647
    assert "region_secured_continue_hover" in [
        event_type for event_type, _payload in events
    ]
    assert "region_secured_continue_click" in [
        event_type for event_type, _payload in events
    ]


def test_post_region_continue_observer_records_next_visible_ui(monkeypatch):
    events = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))
            return payload

    class FakeScreenshots:
        def __init__(self):
            self.frame_clock_sampler = self.sample_clock

        def sample_clock(self):
            return {
                "status": "OK",
                "clock_source": "memory_live_numeric_candidate",
                "game_timer": "0:01:06",
                "game_seconds": 66.0,
            }

        def capture_once(self, *, clock_state, note):
            return {
                "screenshot_path": f"{clock_state}.png",
                "frame_clock_status": "OK",
                "frame_clock": self.sample_clock(),
            }

    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: {
            "status": "OK",
            "visible_ui": "island_map",
            "recommended_control": "archive",
            "region_secured_visible": False,
            "screenshot_path": "island_map.png",
        },
    )

    result = lab.observe_after_region_secured_continue(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        observe_seconds=0.01,
        screenshot_cadence=0.5,
        visible_poll_seconds=0.25,
    )

    assert result["status"] == "OK"
    assert result["first_non_region_visible"]["visible_ui"]["visible_ui"] == (
        "island_map"
    )
    assert result["first_non_region_visible"]["visible_timer"]["game_timer"] == (
        "0:01:06"
    )
    assert "post_region_secured_continue_visible_probe" in [
        event_type for event_type, _payload in events
    ]


def test_terminal_after_end_turn_accepts_inactive_mission_with_stale_heartbeat():
    assert lab._snapshot_terminal_or_clear_after_end_turn(
        {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "active_mechs": 0,
            "deployment_zone_count": 0,
            "in_active_mission": False,
            "bridge_heartbeat_alive": False,
            "bridge_heartbeat_stale": True,
        }
    )


def test_bridge_final_turn_signal_uses_total_turn_count():
    final = lab._bridge_final_turn_signal(
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "total_turns": 4,
            "remaining_spawns": 1,
            "is_infinite_spawn": True,
        }
    )
    not_final = lab._bridge_final_turn_signal(
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "total_turns": 4,
            "remaining_spawns": 0,
        }
    )

    assert final["expected_final_turn"] is True
    assert final["source"] == "bridge_turn_reached_total_turns"
    assert not_final["expected_final_turn"] is False
    assert not_final["source"] == "bridge_turn_before_total_turns"


def test_solve_until_region_secured_repeats_until_terminal(monkeypatch):
    calls = []
    results = [
        {"status": "PASS", "boundary": "player_turn_ready", "reason": "next_turn"},
        {
            "status": "PASS",
            "boundary": "region_secured",
            "reason": "combat_region_secured_visible",
            "first_region_secured_visible": {"visible_ui": {"visible_ui": "reward_panel"}},
            "region_secured_continue_hover": {"status": "OK"},
            "region_secured_continue_click": {"status": "OK"},
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            return {"event_type": event_type, **payload}

    def fake_turn(**kwargs):
        calls.append(kwargs)
        return results.pop(0)

    monkeypatch.setattr(
        lab,
        "solve_execute_end_turn_and_observe_next_turn",
        fake_turn,
    )

    result = lab.solve_until_region_secured(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=object(),
        max_turns=4,
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=30.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.2,
        visible_poll_seconds=0.5,
        terminal_visual_settle_seconds=1.0,
        extra_ready_frames=1,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
        hover_region_continue=True,
        region_continue_hover_seconds=1.0,
        click_region_continue=True,
        region_continue_click_settle_seconds=0.35,
    )

    assert result["status"] == "PASS"
    assert result["reason"] == "region_secured_visible_continue_clicked"
    assert result["turns_attempted"] == 2
    assert result["region_secured"]["visible_ui"]["visible_ui"] == "reward_panel"
    assert result["continue_click"]["status"] == "OK"
    assert len(calls) == 2
    assert all(call["stop_on_region_secured"] is True for call in calls)
    assert all(call["click_region_continue"] is True for call in calls)


def test_solve_until_region_secured_tightens_on_bridge_final_turn(monkeypatch):
    calls = []
    results = [
        {
            "status": "PASS",
            "boundary": "player_turn_ready",
            "reason": "next_turn",
            "first_player_ready_bridge": {
                "snapshot": {
                    "status": "OK",
                    "phase": "combat_player",
                    "turn": 4,
                    "total_turns": 4,
                    "remaining_spawns": 1,
                }
            },
        },
        {
            "status": "PASS",
            "boundary": "region_secured",
            "reason": "combat_region_secured_visible",
            "first_region_secured_visible": {"visible_ui": {"visible_ui": "reward_panel"}},
            "region_secured_continue_hover": {"status": "OK"},
            "region_secured_continue_click": {"status": "OK"},
        },
    ]

    class FakeTelemetry:
        def event(self, event_type, **payload):
            return {"event_type": event_type, **payload}

    def fake_turn(**kwargs):
        result = results.pop(0)
        calls.append({**kwargs, "_result": result})
        return result

    monkeypatch.setattr(
        lab,
        "solve_execute_end_turn_and_observe_next_turn",
        fake_turn,
    )

    result = lab.solve_until_region_secured(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=object(),
        max_turns=3,
        auto_turn_time_limit=10.0,
        auto_turn_max_wait=8.0,
        observe_seconds=30.0,
        screenshot_cadence=0.5,
        bridge_poll_seconds=0.2,
        visible_poll_seconds=0.5,
        terminal_visual_settle_seconds=1.0,
        extra_ready_frames=0,
        pause_after_ready=True,
        retry_after_seconds=2.0,
        continue_after_fuzzy_block=True,
        fuzzy_block_min_actions=3,
        hover_region_continue=True,
        region_continue_hover_seconds=1.0,
        click_region_continue=True,
        region_continue_click_settle_seconds=0.35,
        expected_terminal_after_turn=3,
        expected_terminal_visible_poll_seconds=0.2,
        initial_player_ready_snapshot={
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "total_turns": 4,
            "remaining_spawns": 0,
        },
    )

    assert result["status"] == "PASS"
    assert calls[0]["visible_poll_seconds"] == 0.5
    assert calls[1]["visible_poll_seconds"] == 0.2
    assert result["turns"][0]["expected_final_turn"] is False
    assert result["turns"][0]["expected_final_turn_source"] == (
        "bridge_turn_before_total_turns"
    )
    assert result["turns"][1]["expected_final_turn"] is True
    assert result["turns"][1]["expected_final_turn_source"] == (
        "bridge_turn_reached_total_turns"
    )


def test_followup_mission_from_island_map_runs_full_slice(monkeypatch):
    calls = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            calls.append((event_type, payload))
            return {"event_type": event_type, **payload}

    args = argparse.Namespace(
        profile="Alpha",
        memory_timer_probe=True,
        red_map_timeout_seconds=3.0,
        red_probe_interval_seconds=0.1,
        red_mission_click_hover_seconds=0.01,
        red_mission_click_settle_seconds=0.02,
        red_mission_click_hold_seconds=0.03,
        start_mission_click_settle_seconds=0.04,
        start_mission_click_hover_seconds=0.05,
        start_mission_click_hold_seconds=0.06,
        deployment_timeout_seconds=4.0,
        deployment_probe_interval_seconds=0.1,
        start_mission_pre_click_probe=False,
        post_confirm_observe_seconds=5.0,
        screenshot_cadence=0.5,
        post_confirm_bridge_poll_seconds=0.2,
        post_confirm_extra_ready_frames=0,
        pause_after_opening_player_turn=True,
        combat_loop_max_turns=6,
        combat_auto_turn_time_limit=10.0,
        combat_auto_turn_max_wait=8.0,
        destroy_time_pods=True,
        post_end_turn_observe_seconds=30.0,
        post_end_turn_bridge_poll_seconds=0.2,
        region_secured_visible_poll_seconds=0.5,
        region_secured_terminal_settle_seconds=1.0,
        post_end_turn_extra_ready_frames=0,
        pause_after_combat_player_turn=True,
        end_turn_retry_after_seconds=0.75,
        combat_continue_after_fuzzy_block=True,
        combat_fuzzy_block_min_actions=3,
        region_secured_hover_continue=True,
        region_secured_continue_hover_seconds=1.0,
        region_secured_click_continue=True,
        region_secured_continue_click_settle_seconds=0.35,
        region_secured_post_continue_observe_seconds=0.2,
        region_secured_post_continue_visible_poll_seconds=0.1,
        speed_expected_player_turns=3,
        speed_final_turn_visible_poll_seconds=0.2,
    )

    monkeypatch.setattr(
        lab,
        "wait_for_archive_red_map",
        lambda **kwargs: {
            "status": "PASS",
            "detected_frame_timer": {"game_timer": "0:02:21", "game_seconds": 141.0},
            "paired_in_game_timer": {"game_timer": "0:02:21", "game_seconds": 141.1},
            "selected_region": {"window_x": 100, "window_y": 200},
        },
    )
    monkeypatch.setattr(
        lab,
        "click_selected_red_mission_preview",
        lambda **kwargs: {
            "status": "OK",
            "preview_frame_timer": {"game_timer": "0:02:22", "game_seconds": 142.0},
            "after_preview_timer": {"game_timer": "0:02:22", "game_seconds": 142.2},
        },
    )
    monkeypatch.setattr(
        lab,
        "click_start_mission_from_preview",
        lambda **kwargs: {
            "status": "PASS",
            "before_in_game_timer": {"game_timer": "0:02:23", "game_seconds": 143.0},
            "samples": [
                {
                    "deployment_visible": True,
                    "frame_timer": {"game_timer": "0:02:24", "game_seconds": 144.0},
                }
            ],
        },
    )
    monkeypatch.setattr(
        lab,
        "deploy_recommended_after_visible_deployment",
        lambda **kwargs: {
            "status": "PASS",
            "before_in_game_timer": {"game_timer": "0:02:24", "game_seconds": 144.0},
            "after_in_game_timer": {"game_timer": "0:02:25", "game_seconds": 145.0},
        },
    )
    monkeypatch.setattr(
        lab,
        "confirm_deployment_and_observe_opening_turn",
        lambda **kwargs: {
            "status": "PASS",
            "before_in_game_timer": {"game_timer": "0:02:26", "game_seconds": 146.0},
            "first_player_ready_bridge": {
                "bridge_timer": {"game_timer": "0:02:36", "game_seconds": 156.0},
                "snapshot": {"status": "OK", "phase": "combat_player", "turn": 1},
            },
        },
    )
    monkeypatch.setattr(
        lab,
        "solve_until_region_secured",
        lambda **kwargs: {
            "status": "PASS",
            "reason": "region_secured_visible_continue_clicked",
            "turns": [],
            "region_secured": {
                "visible_timer": {"game_timer": "0:04:08", "game_seconds": 248.0}
            },
            "continue_click": {
                "before_in_game_timer": {
                    "game_timer": "0:04:09",
                    "game_seconds": 249.0,
                },
                "after_frame_timer": {
                    "game_timer": "0:04:10",
                    "game_seconds": 250.0,
                },
            },
        },
    )

    result = lab.run_followup_mission_from_island_map(
        mission_index=2,
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=object(),
        args=args,
        memory_timer_address=None,
        memory_live_timer_address=0x1234,
        memory_live_timer_kind="f32_seconds",
        deployment_trigger_source="screenshot_yellow",
    )

    assert result["status"] == "PASS"
    assert result["mission_index"] == 2
    assert result["in_game_timers"]["region_secured_visible"]["game_timer"] == "0:04:08"
    assert result["turn_timing_audit"]["status"] in {"OK", "NO_DATA"}
    assert [event_type for event_type, _payload in calls] == [
        "followup_mission_start",
        "followup_mission_result",
    ]


def test_build_turn_timing_audit_counts_sequence_and_deltas():
    def timer(text, seconds):
        return {"game_timer": text, "game_seconds": seconds}

    report = {
        "in_game_timers": {
            "deploy_confirm_click_before": timer("0:00:12", 12.0),
        },
        "deploy_confirm": {
            "first_player_ready_bridge": {
                "bridge_timer": timer("0:00:23", 23.0),
            },
            "first_player_ready_frame_after_bridge": {
                "frame_timer": timer("0:00:23", 23.4),
            },
        },
        "combat_until_region_secured": {
            "turns": [
                {
                    "loop_turn_index": 1,
                    "before_in_game_timer": timer("0:00:24", 24.0),
                    "auto_turn_done_timer": timer("0:00:30", 30.0),
                    "end_turn_before_in_game_timer": timer("0:00:36", 36.0),
                    "auto_turn_duration_seconds": 6.0,
                    "auto_turn_summary": {"actions_completed": 3},
                    "boundary": "player_turn_ready",
                    "first_non_player_bridge": {
                        "bridge_timer": timer("0:00:41", 41.0),
                    },
                    "first_player_ready_bridge": {
                        "bridge_timer": timer("0:00:47", 47.0),
                        "snapshot": {"turn": 2},
                    },
                    "first_player_ready_frame_after_bridge": {
                        "frame_timer": timer("0:00:47", 47.5),
                    },
                    "after_pause_timer": timer("0:00:47", 47.7),
                },
                {
                    "loop_turn_index": 2,
                    "before_in_game_timer": timer("0:00:48", 48.0),
                    "end_turn_before_in_game_timer": timer("0:01:00", 60.0),
                    "auto_turn_summary": {"actions_completed": 3},
                    "boundary": "region_secured",
                    "first_region_secured_visible": {
                        "visible_timer": timer("0:01:18", 78.0),
                        "elapsed_after_end_turn_seconds": 18.2,
                    },
                },
            ],
        },
    }

    audit = lab.build_turn_timing_audit(report)

    assert audit["status"] == "OK"
    assert audit["player_turn_count"] == 2
    assert audit["enemy_phase_count"] == 3
    assert audit["sequence_text"] == (
        "enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2->done"
    )
    assert audit["post_end_turn_to_next_player_seconds"]["values"] == [11.0]
    assert audit["end_turn_to_enemy_bridge_seconds"]["values"] == [5.0]
    assert audit["enemy_bridge_to_next_player_seconds"]["values"] == [6.0]
    assert audit["ready_bridge_to_first_frame_seconds"]["values"] == [0.5]
    assert audit["ready_bridge_to_pause_seconds"]["values"] == [0.7]
    assert (
        audit["terminal_phase"]["end_turn_to_region_secured_visible_seconds"]
        == 18.0
    )


def test_speed_sequence_expectation_matches_short_route():
    audit = {
        "sequence_text": "enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done",
        "player_turn_count": 3,
        "enemy_phase_count": 4,
    }

    result = lab.evaluate_speed_sequence_expectation(
        audit,
        expected_player_turns=3,
    )

    assert result["status"] == "MATCH"
    assert result["expected_player_turn_count"] == 3
    assert result["expected_enemy_phase_count"] == 4
    assert result["expected_sequence"] == audit["sequence_text"]


def test_speed_sequence_expectation_flags_long_route_mismatch():
    audit = {
        "sequence_text": "enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3 -> us4 -> enemy4->done",
        "player_turn_count": 4,
        "enemy_phase_count": 5,
    }

    result = lab.evaluate_speed_sequence_expectation(
        audit,
        expected_player_turns=3,
    )

    assert result["status"] == "MISMATCH"
    assert result["fallback"] == (
        "continue_dynamic_loop_if_expected_terminal_turn_returns_player_ready"
    )


def test_build_parser_defaults_match_first_milestone():
    args = lab.build_parser().parse_args([])

    assert args.screenshot_cadence == 0.5
    assert args.island_click_seconds == 7.0
    assert args.continue_click_seconds == 9.5
    assert args.red_map_timeout_seconds == 10.0
    assert args.memory_timer_probe is True
    assert args.memory_timer_address is None
    assert args.memory_live_timer_proof is None
    assert args.auto_memory_live_timer_proof is True
    assert args.require_memory_live_timer_proof is False
    assert args.click_red_mission is False
    assert args.click_start_mission is False
    assert args.start_mission_click_hover_seconds == 0.05
    assert args.start_mission_pre_click_probe is False
    assert args.deployment_trigger_source == "visible-ui"
    assert args.pause_after_red_mission_click is True
    assert args.pause_after_start_mission_click is True
    assert args.deploy_after_visible_deployment is False
    assert args.pause_after_deploy_recommended is True
    assert args.confirm_after_deploy is False
    assert args.post_confirm_observe_seconds == 30.0
    assert args.post_confirm_bridge_poll_seconds == 0.2
    assert args.post_confirm_extra_ready_frames == 0
    assert args.pause_after_opening_player_turn is True
    assert args.combat_turn_after_confirm is False
    assert args.combat_until_region_secured is False
    assert args.current_combat_until_region_secured is False
    assert args.combat_auto_turn_time_limit == 10.0
    assert args.combat_auto_turn_max_wait == 8.0
    assert args.combat_loop_max_turns == 6
    assert args.speed_expected_player_turns == 3
    assert args.speed_final_turn_visible_poll_seconds == 0.2
    assert args.post_end_turn_observe_seconds == 30.0
    assert args.post_end_turn_bridge_poll_seconds == 0.2
    assert args.post_end_turn_extra_ready_frames == 0
    assert args.end_turn_retry_after_seconds == 0.75
    assert args.region_secured_visible_poll_seconds == 0.5
    assert args.region_secured_terminal_settle_seconds == 1.0
    assert args.region_secured_continue_hover_seconds == 1.0
    assert args.region_secured_continue_click_settle_seconds == 0.35
    assert args.region_secured_post_continue_observe_seconds == 8.0
    assert args.region_secured_post_continue_visible_poll_seconds == 0.25
    assert args.region_secured_hover_continue is True
    assert args.region_secured_click_continue is True
    assert args.combat_continue_after_fuzzy_block is True
    assert args.combat_fuzzy_block_min_actions == 3
    assert args.combat_auto_consent_safety_block is True
    assert args.pause_after_combat_player_turn is True


def test_timer_sample_seconds_rejects_unvalidated_save_fallback():
    assert (
        lab._timer_sample_seconds(
            {
                "status": "OK",
                "clock_source": "save_current_time",
                "game_timer": "0:00:04",
                "game_seconds": 4.0,
            }
        )
        is None
    )


def test_read_memory_timer_rejects_values_over_lightning_limit(monkeypatch):
    class FakeReader:
        def __init__(self, pid):
            self.pid = pid

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

    monkeypatch.setattr(lab.os, "name", "nt")
    monkeypatch.setattr(lab.memory_probe, "_find_breach_pid", lambda: 123)
    monkeypatch.setattr(lab.memory_probe, "WindowsProcessReader", FakeReader)
    monkeypatch.setattr(lab.memory_probe, "scan_context_timers", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        lab.memory_probe,
        "select_visible_timer_context",
        lambda _context, **_kwargs: {"seconds": 29792.0, "game_timer": "8:16:32"},
    )

    result = lab._read_memory_in_game_timer(label="red_map")

    assert result["status"] == "REJECTED"
    assert result["game_timer"] == "8:16:32"


def test_read_memory_timer_uses_calibrated_timeline_address(monkeypatch):
    class FakeReader:
        def __init__(self, pid):
            self.pid = pid

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

        def read(self, address, size):
            assert address == 0x138A5900
            return b"0h 1m 04s\x00"

    monkeypatch.setattr(lab.os, "name", "nt")
    monkeypatch.setattr(lab.memory_probe, "_find_breach_pid", lambda: 123)
    monkeypatch.setattr(lab.memory_probe, "WindowsProcessReader", FakeReader)

    result = lab._read_memory_in_game_timer(
        label="pause_check",
        timer_address=0x138A5900,
    )

    assert result["status"] == "OK"
    assert result["clock_source"] == "memory_timeline_playtime_address"
    assert result["address"] == "0x00000000138a5900"
    assert result["game_seconds"] == 64.0
    assert result["timer_validation"] == "pause_menu_render_cache_not_live_clock"
    assert result["live_clock_usable"] is False


def test_frame_clock_sampler_requires_calibrated_address(monkeypatch):
    assert lab.make_frame_clock_sampler(use_memory=False, timer_address=0x138A5900) is None
    assert lab.make_frame_clock_sampler(use_memory=True, timer_address=None) is None
    assert lab.make_frame_clock_sampler(use_memory=True, timer_address=0x138A5900) is None


def test_frame_clock_sampler_reads_live_numeric_candidate(monkeypatch):
    opened = {"count": 0}

    class FakeReader:
        def __init__(self, pid):
            opened["count"] += 1
            self.pid = pid

        def close(self):
            return None

    monkeypatch.setattr(lab.os, "name", "nt")
    monkeypatch.setattr(lab.memory_probe, "_find_breach_pid", lambda: 123)
    monkeypatch.setattr(lab.memory_probe, "WindowsProcessReader", FakeReader)
    monkeypatch.setattr(
        lab.memory_probe,
        "read_numeric_timer_address",
        lambda reader, address, kind: {
            "read_ok": True,
            "address": f"0x{address:016x}",
            "kind": kind,
            "seconds": 1271.635132,
            "game_timer": "0:21:11",
            "raw_value": 1271.635132,
        },
    )

    sampler = lab.make_frame_clock_sampler(
        use_memory=True,
        timer_address=None,
        live_timer_address=0x122E5DBC,
        live_timer_kind="f32_seconds",
    )

    assert sampler is not None
    sample = sampler()
    second = sampler()
    assert sample["clock_source"] == "memory_live_numeric_candidate"
    assert sample["timer_validation"] == "validated_live_numeric_cycle"
    assert sample["game_timer"] == "0:21:11"
    assert sample["address"] == "0x00000000122e5dbc"
    assert second["game_seconds"] == 1271.635132
    assert opened["count"] == 1


def test_resolve_live_timer_config_uses_validated_proof(monkeypatch, tmp_path):
    proof_path = tmp_path / "proof.json"
    proof_path.write_text('{"status": "OK"}\n', encoding="utf-8")
    monkeypatch.setattr(
        lab.memory_probe,
        "validate_session_clock_proof",
        lambda proof, **_kwargs: {
            "status": "OK",
            "address": "0x0000000010e144fc",
            "kind": "f32_seconds",
            "game_timer": "0:02:13",
        },
    )
    args = lab.build_parser().parse_args(
        ["--memory-live-timer-proof", str(proof_path)]
    )

    address, kind, validation = lab._resolve_live_timer_config(args)

    assert address == 0x10E144FC
    assert kind == "f32_seconds"
    assert validation["proof_path"] == str(proof_path)


def test_resolve_live_timer_config_auto_uses_default_proof(monkeypatch, tmp_path):
    default_proof = tmp_path / "recordings" / "lightning_session_clock_proof.json"
    default_proof.parent.mkdir(parents=True)
    default_proof.write_text('{"status": "OK"}\n', encoding="utf-8")
    monkeypatch.setattr(lab, "ROOT", tmp_path)
    monkeypatch.setattr(
        lab.memory_probe,
        "validate_session_clock_proof",
        lambda proof, **_kwargs: {
            "status": "OK",
            "address": "0x0000000010e144fc",
            "kind": "f32_seconds",
        },
    )
    args = lab.build_parser().parse_args([])

    address, kind, validation = lab._resolve_live_timer_config(args)

    assert address == 0x10E144FC
    assert kind == "f32_seconds"
    assert validation["proof_path"] == str(default_proof)
    assert validation["proof_selection"] == "auto_default"


def test_resolve_live_timer_config_requires_proof_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "ROOT", tmp_path)
    args = lab.build_parser().parse_args(["--require-memory-live-timer-proof"])

    try:
        lab._resolve_live_timer_config(args)
    except RuntimeError as exc:
        assert "memory live timer proof required but missing" in str(exc)
    else:
        raise AssertionError("expected missing proof to fail")


def test_followup_preview_transition_reads_live_timer(monkeypatch):
    events = []
    timer_calls = []

    class FakeTelemetry:
        def event(self, event_type, **payload):
            events.append((event_type, payload))

    class FakeScreenshots:
        pass

    def fake_read_timer(profile, **kwargs):
        timer_calls.append((profile, kwargs))
        return {
            "status": "OK",
            "label": kwargs["label"],
            "clock_source": "memory_live_numeric_candidate",
            "game_timer": "0:02:03",
            "game_seconds": 123.0,
        }

    monkeypatch.setattr(lab, "_elapsed", lambda start: 12.5)
    monkeypatch.setattr(lab, "read_in_game_timer", fake_read_timer)
    monkeypatch.setattr(
        lab,
        "click_start_mission_from_preview",
        lambda **_kwargs: {"status": "FAIL", "reason": "stubbed_start"},
    )
    args = lab.build_parser().parse_args(["--profile", "Beta"])

    result = lab.run_followup_mission_from_island_map(
        mission_index=2,
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        args=args,
        memory_timer_address=0x138A5900,
        memory_live_timer_address=0x122E5DBC,
        memory_live_timer_kind="f32_seconds",
        deployment_trigger_source="screenshot_yellow",
        preview_transition={
            "status": "MISSION_PREVIEW_OPENED",
            "red_region": {"index": 0, "window_x": 100, "window_y": 200},
        },
    )

    assert result["status"] == "FAIL"
    assert result["mission_preview"]["after_preview_timer"]["game_seconds"] == 123.0
    assert timer_calls == [
        (
            "Beta",
            {
                "label": "mission_preview_after_result_clear",
                "use_memory": True,
                "timer_address": 0x138A5900,
                "live_timer_address": 0x122E5DBC,
                "live_timer_kind": "f32_seconds",
            },
        )
    ]
    assert any(
        event_type == "followup_mission_preview_opened_by_result_clear"
        for event_type, _payload in events
    )


def test_update_profile_keeps_faster_existing_pass(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(lab, "PROFILE_PATH", profile_path)
    profile_path.write_text(
        """
{
  "schema_version": 1,
  "current_milestone": "main_menu_to_archive_red_map",
  "updated_at": "old",
  "boundaries": {
    "main_menu_to_archive_red_map": {
      "status": "PASS",
      "red_map_detected_wall_seconds": 19.276,
      "evidence": {"run_id": "fast"}
    }
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    lab.update_profile(
        {
            "status": "PASS",
            "branch_label": "archive_intro.default",
            "run_id": "slow",
            "marks": {"archive_click": 7.978, "intro_continue": 10.315},
            "red_detection": {
                "detected_at_seconds": 19.413,
                "region_count": 2,
                "selected_region": {"window_x": 1806, "window_y": 703},
            },
        }
    )

    result = lab._load_profile()
    boundary = result["boundaries"]["main_menu_to_archive_red_map"]
    assert boundary["red_map_detected_wall_seconds"] == 19.276
    assert boundary["evidence"]["run_id"] == "fast"


def test_update_profile_promotes_in_game_timer_over_wall_only_pass(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(lab, "PROFILE_PATH", profile_path)
    profile_path.write_text(
        """
{
  "schema_version": 1,
  "current_milestone": "main_menu_to_archive_red_map",
  "updated_at": "old",
  "boundaries": {
    "main_menu_to_archive_red_map": {
      "status": "PASS",
      "red_map_detected_wall_seconds": 19.276,
      "red_map_detected_game_seconds": null,
      "evidence": {"run_id": "wall-only"}
    }
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    lab.update_profile(
        {
            "status": "PASS",
            "branch_label": "archive_intro.default",
            "run_id": "game-timer",
            "marks": {"archive_click": 8.0, "intro_continue": 10.0},
            "in_game_timers": {
                "red_map_detected": {
                    "status": "OK",
                    "clock_source": "memory_live_numeric_candidate",
                    "source": "validated_live_numeric_cycle",
                    "game_timer": "0:00:06",
                    "game_seconds": 6.0,
                    "game_timer_ms": 6000.0,
                }
            },
            "red_detection": {
                "detected_at_seconds": 20.0,
                "region_count": 2,
                "selected_region": {"window_x": 1806, "window_y": 703},
            },
        }
    )

    result = lab._load_profile()
    boundary = result["boundaries"]["main_menu_to_archive_red_map"]
    assert boundary["red_map_detected_game_seconds"] == 6.0
    assert boundary["evidence"]["run_id"] == "game-timer"
