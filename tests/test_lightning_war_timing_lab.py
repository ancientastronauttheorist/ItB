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
    assert boundary["time_source"] == "wall_clock_perf_counter"
    assert boundary["archive_click_wall_seconds"] == 7.0
    assert boundary["red_map_detected_wall_seconds"] == 10.25
    assert boundary["in_game_timer"]["status"] == "NOT_RECORDED"
    assert boundary["region_count"] == 5
    assert boundary["chosen_probe_region"]["window_x"] == 620
    assert boundary["evidence"]["contact_sheet_path"] == "contact.png"


def test_wait_for_archive_red_map_returns_pass_on_first_region(monkeypatch):
    events = []
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

    result = lab.wait_for_archive_red_map(
        timer_start=0.0,
        telemetry=FakeTelemetry(),
        screenshots=FakeScreenshots(),
        max_seconds=2.0,
        interval_seconds=0.01,
    )

    assert result["status"] == "PASS"
    assert result["region_count"] == 1
    assert result["selected_region"]["window_x"] == 500
    assert any(event_type == "opening_red_region_probe" for event_type, _ in events)


def test_build_parser_defaults_match_first_milestone():
    args = lab.build_parser().parse_args([])

    assert args.screenshot_cadence == 0.5
    assert args.island_click_seconds == 7.0
    assert args.continue_click_seconds == 9.5
    assert args.red_map_timeout_seconds == 10.0


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
