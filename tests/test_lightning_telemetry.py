import json

from PIL import Image

from src.loop.lightning_telemetry import TelemetryRecorder, generate_frame_delta_report


def test_telemetry_writes_required_attempt_artifacts(tmp_path):
    recorder = TelemetryRecorder("lw_test", root=tmp_path)
    recorder.write_manifest({"achievement": "Lightning War"})
    recorder.event("clock_sample", game_timer="0:01:00", game_seconds=60)

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
    assert report["status"] == "OK"
    rows = [
        json.loads(line)
        for line in (telemetry / "frame_deltas.jsonl").read_text().splitlines()
    ]
    assert rows[0]["interesting"] is True
    assert rows[1]["delta_score"] > 0
