import json
import os
from pathlib import Path

from PIL import Image

from src.loop.lightning_telemetry import (
    ScreenshotRecorder,
    TelemetryRecorder,
    generate_frame_delta_report,
    prune_lightning_screenshot_runs,
)


def test_telemetry_writes_required_attempt_artifacts(tmp_path):
    recorder = TelemetryRecorder("lw_test", root=tmp_path)
    recorder.write_manifest({"achievement": "Lightning War"})
    recorder.event("clock_sample", game_timer="0:01:00", game_seconds=60)
    recorder.progress_ledger(
        burst_label="lightning_segment",
        before_state="ui:pause_menu",
        after_state="segment_progress",
        timer_before="0:01:00",
        timer_before_seconds=60.0,
        timer_after="0:01:12",
        timer_after_seconds=72.0,
        timer_delta_seconds=12.0,
        result="progress",
    )
    recorder.timer_hygiene(
        burst_label="lightning_segment",
        timer_before="0:01:00",
        timer_before_seconds=60.0,
        timer_after="0:01:12",
        timer_after_seconds=72.0,
        timer_delta_seconds=12.0,
        classification="productive_clock",
    )

    first = recorder.screenshots_dir / "000001.png"
    second = recorder.screenshots_dir / "000002.png"
    Image.new("RGB", (64, 64), (10, 10, 10)).save(first)
    Image.new("RGB", (64, 64), (230, 230, 230)).save(second)
    recorder.frame(dropped=False, screenshot_path=str(first))
    recorder.frame(dropped=False, screenshot_path=str(second))
    recorder.summary(status="PARKED_SAFE", reason="test")

    report = generate_frame_delta_report(tmp_path / "lw_test")

    telemetry = tmp_path / "lw_test" / "telemetry"
    assert (telemetry / "manifest.json").exists()
    assert (telemetry / "events.jsonl").exists()
    assert (telemetry / "frames.jsonl").exists()
    assert (telemetry / "summary.md").exists()
    assert (telemetry / "frame_deltas.jsonl").exists()
    assert (telemetry / "interesting_frames.md").exists()
    assert (telemetry / "contact_sheet.png").exists()
    summary = (telemetry / "summary.md").read_text()
    assert "Progress ledger events: 1" in summary
    assert "Timer hygiene events: 1" in summary
    assert "Progress results: progress=1" in summary
    assert "Positive timer by result: progress=12.0s" in summary
    assert "Timer hygiene classes: productive_clock=1" in summary
    assert "Positive timer by hygiene class: productive_clock=12.0s" in summary
    events = [
        json.loads(line)
        for line in (telemetry / "events.jsonl").read_text().splitlines()
    ]
    assert events[1]["event_type"] == "progress_ledger"
    assert events[1]["burst_label"] == "lightning_segment"
    assert events[2]["event_type"] == "timer_hygiene"
    assert report["status"] == "OK"
    rows = [
        json.loads(line)
        for line in (telemetry / "frame_deltas.jsonl").read_text().splitlines()
    ]
    assert rows[0]["interesting"] is True
    assert rows[1]["delta_score"] > 0


def test_screenshot_recorder_prunes_to_retention_window(tmp_path, monkeypatch):
    recorder = TelemetryRecorder("lw_test", root=tmp_path)
    capture_index = {"value": 0}

    def fake_capture_game_window(path: Path) -> dict:
        capture_index["value"] += 1
        shade = capture_index["value"] * 40
        Image.new("RGB", (8, 8), (shade, shade, shade)).save(path)
        return {"status": "OK", "bounds": {"width": 8, "height": 8}}

    monkeypatch.setattr(
        "src.loop.lightning_telemetry.capture_game_window",
        fake_capture_game_window,
    )
    screenshots = ScreenshotRecorder(
        recorder,
        cadence_seconds=0.5,
        max_retained_frames=2,
    )

    rows = [
        screenshots.capture_once(clock_state="turn_1"),
        screenshots.capture_once(clock_state="turn_2"),
        screenshots.capture_once(clock_state="turn_3"),
    ]

    captured_paths = [Path(str(row["screenshot_path"])) for row in rows]
    assert not captured_paths[0].exists()
    assert captured_paths[1].exists()
    assert captured_paths[2].exists()
    assert len(list(recorder.screenshots_dir.glob("*.png"))) == 2

    frame_rows = [
        json.loads(line)
        for line in recorder.frames_path.read_text().splitlines()
    ]
    assert [row["clock_state"] for row in frame_rows] == [
        "turn_1",
        "turn_2",
        "turn_3",
    ]


def test_screenshot_recorder_prunes_old_clock_state_groups(tmp_path, monkeypatch):
    recorder = TelemetryRecorder("lw_test", root=tmp_path)
    capture_index = {"value": 0}

    def fake_capture_game_window(path: Path) -> dict:
        capture_index["value"] += 1
        shade = capture_index["value"] * 30
        Image.new("RGB", (8, 8), (shade, shade, shade)).save(path)
        return {"status": "OK", "bounds": {"width": 8, "height": 8}}

    monkeypatch.setattr(
        "src.loop.lightning_telemetry.capture_game_window",
        fake_capture_game_window,
    )
    screenshots = ScreenshotRecorder(
        recorder,
        cadence_seconds=0.5,
        max_retained_frames=None,
        max_retained_clock_states=3,
    )

    rows = [
        screenshots.capture_once(clock_state="turn_1"),
        screenshots.capture_once(clock_state="turn_1"),
        screenshots.capture_once(clock_state="turn_2"),
        screenshots.capture_once(clock_state="turn_3"),
        screenshots.capture_once(clock_state="turn_4"),
    ]

    captured_paths = [Path(str(row["screenshot_path"])) for row in rows]
    assert not captured_paths[0].exists()
    assert not captured_paths[1].exists()
    assert captured_paths[2].exists()
    assert captured_paths[3].exists()
    assert captured_paths[4].exists()
    assert len(list(recorder.screenshots_dir.glob("*.png"))) == 3


def test_screenshot_recorder_includes_game_timer_in_filename(tmp_path, monkeypatch):
    recorder = TelemetryRecorder("lw_test", root=tmp_path)

    def fake_capture_game_window(path: Path) -> dict:
        Image.new("RGB", (8, 8), (80, 80, 80)).save(path)
        return {"status": "OK", "bounds": {"width": 8, "height": 8}}

    monkeypatch.setattr(
        "src.loop.lightning_telemetry.capture_game_window",
        fake_capture_game_window,
    )
    screenshots = ScreenshotRecorder(
        recorder,
        cadence_seconds=0.5,
        frame_clock_sampler=lambda: {
            "status": "OK",
            "clock_source": "memory_timeline_playtime_address",
            "game_timer": "0:01:04",
            "game_seconds": 64.0,
            "address": "0x00000000138a5900",
        },
    )

    row = screenshots.capture_once(clock_state="opening_probe")
    path = Path(str(row["screenshot_path"]))

    assert "_gt0-01-04_" in path.name
    assert row["game_timer"] == "0:01:04"
    assert row["game_seconds"] == 64.0
    assert row["frame_clock"]["address"] == "0x00000000138a5900"
    assert row["clock_source"] == "memory_timeline_playtime_address"


def test_prune_lightning_screenshot_runs_keeps_newest_three(tmp_path):
    recordings = tmp_path / "recordings"
    run_notes = tmp_path / "run_notes"
    run_keys = [
        "20260626_000001_000",
        "20260626_000002_000",
        "20260626_000003_000",
        "20260626_000004_000",
    ]
    for index, run_id in enumerate(run_keys, start=1):
        screenshots = recordings / run_id / "telemetry" / "screenshots"
        screenshots.mkdir(parents=True)
        image = screenshots / "frame.png"
        Image.new("RGB", (4, 4), (index, index, index)).save(image)
        mtime = 1_800_000_000 + index
        os.utime(image, (mtime, mtime))
        os.utime(screenshots, (mtime, mtime))
        os.utime(recordings / run_id, (mtime, mtime))
    old_notes = run_notes / "lightning_war_smoke_2026-06-01" / "screenshots"
    old_notes.mkdir(parents=True)
    Image.new("RGB", (4, 4), (1, 1, 1)).save(old_notes / "old.png")
    top_level_note = run_notes / "old_probe.png"
    Image.new("RGB", (4, 4), (1, 1, 1)).save(top_level_note)
    old_mtime = 1_700_000_000
    os.utime(old_notes / "old.png", (old_mtime, old_mtime))
    os.utime(old_notes, (old_mtime, old_mtime))
    os.utime(top_level_note, (old_mtime, old_mtime))

    result = prune_lightning_screenshot_runs(
        recordings_root=recordings,
        run_notes_root=run_notes,
        max_runs=3,
    )

    assert result["status"] == "OK"
    assert set(result["retained_run_keys"]) == set(run_keys[-3:])
    assert not (recordings / run_keys[0] / "telemetry" / "screenshots").exists()
    assert not old_notes.exists()
    assert not top_level_note.exists()
    for run_id in run_keys[-3:]:
        assert (recordings / run_id / "telemetry" / "screenshots").exists()


def test_telemetry_recorder_applies_screenshot_run_retention(tmp_path):
    recordings = tmp_path / "recordings"
    for index in range(4):
        run_id = f"20260626_00000{index}_000"
        screenshots = recordings / run_id / "telemetry" / "screenshots"
        screenshots.mkdir(parents=True)
        image = screenshots / "frame.png"
        Image.new("RGB", (4, 4), (index, index, index)).save(image)
        mtime = 1_800_000_000 + index
        os.utime(image, (mtime, mtime))
        os.utime(screenshots, (mtime, mtime))

    recorder = TelemetryRecorder("20260626_000004_000", root=recordings)

    assert recorder.retention_result["status"] == "OK"
    assert not (
        recordings / "20260626_000000_000" / "telemetry" / "screenshots"
    ).exists()
