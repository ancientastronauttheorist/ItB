from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lightning_war_timing_lab.py"
SPEC = importlib.util.spec_from_file_location("lightning_war_timing_lab", SCRIPT)
lab = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = lab
SPEC.loader.exec_module(lab)


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
    assert screenshots.calls == [
        ("deployment_probe", "after_start_mission_click"),
        ("deployment_probe", "after_start_mission_click"),
    ]
    assert [event_type for event_type, _payload in events] == [
        "mission_preview_pre_start_probe_skipped",
        "start_mission_click",
        "deployment_probe",
        "deployment_probe",
        "deployment_pause",
    ]
    assert visible_calls["count"] == 2
    assert events[2][1]["bridge_deployment_ready"] is True
    assert events[2][1]["deployment_visible"] is False
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

    monkeypatch.setattr(
        lab.fast,
        "_lightning_visible_ui_snapshot",
        lambda include_ocr=False: (_ for _ in ()).throw(
            AssertionError("slow visible classifier should be skipped")
        ),
    )
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
    assert yellow_calls["count"] == 2
    assert live_snapshot_calls["count"] == 0
    assert events[2][1]["deployment_yellow_signal"]["yellow"] == 300
    assert events[2][1]["visible_ui"] is None
    assert events[3][1]["deployment_yellow_signal"]["yellow"] == 6500
    assert result["first_bridge_deployment_sample"] is None


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
        {"profile": "Alpha", "ui_fallback": True, "verify_after": False}
    ]
    assert result["deploy_result_compact"]["deployment_count"] == 3
    assert result["before_in_game_timer"]["label"] == "deploy_recommended_trigger_frame"
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


def test_build_parser_defaults_match_first_milestone():
    args = lab.build_parser().parse_args([])

    assert args.screenshot_cadence == 0.5
    assert args.island_click_seconds == 7.0
    assert args.continue_click_seconds == 9.5
    assert args.red_map_timeout_seconds == 10.0
    assert args.memory_timer_probe is True
    assert args.memory_timer_address is None
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
    assert args.post_confirm_extra_ready_frames == 1
    assert args.pause_after_opening_player_turn is True


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
