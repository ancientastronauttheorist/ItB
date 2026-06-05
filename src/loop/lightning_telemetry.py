"""Telemetry helpers for Lightning War autonomous attempts."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # pragma: no cover - only used on stripped environments
    Image = None
    ImageChops = None
    ImageStat = None


SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _git_text(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def code_version() -> dict[str, Any]:
    return {
        "git_head": _git_text(["rev-parse", "HEAD"]),
        "git_branch": _git_text(["branch", "--show-current"]),
        "git_dirty": bool(_git_text(["status", "--short"])),
    }


def _event_base(run_id: str, event_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"evt_{uuid.uuid4().hex}",
        "run_id": run_id,
        "event_type": event_type,
        "wall_time": _now_iso(),
        "wall_unix": time.time(),
        "monotonic_ns": time.monotonic_ns(),
    }


@dataclass
class TelemetryRecorder:
    run_id: str
    root: Path = Path("recordings")

    def __post_init__(self) -> None:
        self.run_dir = self.root / self.run_id
        self.telemetry_dir = self.run_dir / "telemetry"
        self.screenshots_dir = self.telemetry_dir / "screenshots"
        self.events_path = self.telemetry_dir / "events.jsonl"
        self.frames_path = self.telemetry_dir / "frames.jsonl"
        self.summary_path = self.telemetry_dir / "summary.md"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write_manifest(self, payload: dict[str, Any]) -> None:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": _now_iso(),
            "code_version": code_version(),
            **payload,
        }
        (self.telemetry_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def event(self, event_type: str, **payload: Any) -> dict[str, Any]:
        row = {**_event_base(self.run_id, event_type), **payload}
        with self._lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def frame(self, **payload: Any) -> dict[str, Any]:
        row = {**_event_base(self.run_id, "screenshot_frame"), **payload}
        with self._lock:
            with self.frames_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def summary(self, *, status: str, reason: str, extra: dict[str, Any] | None = None) -> None:
        events = _load_jsonl(self.events_path)
        frames = _load_jsonl(self.frames_path)
        timers = [
            event.get("game_timer")
            for event in events
            if event.get("game_timer")
        ]
        lines = [
            f"# Lightning War Telemetry - {self.run_id}",
            "",
            f"- Status: {status}",
            f"- Reason: {reason}",
            f"- Events: {len(events)}",
            f"- Frames captured: {sum(1 for frame in frames if not frame.get('dropped'))}",
            f"- Frames dropped: {sum(1 for frame in frames if frame.get('dropped'))}",
            f"- First timer: {timers[0] if timers else ''}",
            f"- Last timer: {timers[-1] if timers else ''}",
        ]
        if extra:
            lines.append("- Extra:")
            for key, value in sorted(extra.items()):
                lines.append(f"  - {key}: {value}")
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ScreenshotRecorder:
    """Best-effort 2-second sampler with backpressure logging."""

    def __init__(
        self,
        telemetry: TelemetryRecorder,
        *,
        cadence_seconds: float = 2.0,
    ) -> None:
        self.telemetry = telemetry
        self.cadence_seconds = max(0.5, float(cadence_seconds))
        self._stop = threading.Event()
        self._capture_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._index = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="lightning-screens", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.cadence_seconds + 1.0))

    def _run(self) -> None:
        next_at = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            if now < next_at:
                self._stop.wait(next_at - now)
                continue
            next_at = max(next_at + self.cadence_seconds, time.monotonic() + self.cadence_seconds)
            self.capture_once(clock_state="sampled")

    def capture_once(self, *, clock_state: str, note: str = "") -> dict[str, Any]:
        if not self._capture_lock.acquire(blocking=False):
            return self.telemetry.frame(
                dropped=True,
                drop_reason="capture_backpressure",
                clock_state=clock_state,
                note=note,
            )
        try:
            self._index += 1
            name = f"{self._index:06d}_{int(time.time() * 1000)}_{clock_state}.png"
            path = self.telemetry.screenshots_dir / name
            started = time.monotonic()
            result = capture_game_window(path)
            latency = round(time.monotonic() - started, 3)
            if result.get("status") != "OK":
                return self.telemetry.frame(
                    dropped=True,
                    drop_reason=result.get("error") or result.get("reason") or "capture_failed",
                    capture_latency_seconds=latency,
                    clock_state=clock_state,
                    note=note,
                )
            return self.telemetry.frame(
                dropped=False,
                screenshot_path=str(path),
                capture_latency_seconds=latency,
                clock_state=clock_state,
                note=note,
                bounds=result.get("bounds"),
            )
        finally:
            self._capture_lock.release()


def capture_game_window(path: Path) -> dict[str, Any]:
    try:
        from src.control.mac_click import _get_window_bounds
    except Exception as exc:
        return {"status": "ERROR", "error": f"window bounds import failed: {exc}"}
    bounds = _get_window_bounds("Into the Breach")
    if bounds is None:
        return {"status": "ERROR", "error": "could not read Into the Breach window bounds"}
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        if Image is None:
            return {"status": "ERROR", "error": "Pillow is required on Windows"}
        try:
            from PIL import ImageGrab

            bbox = (
                int(bounds["x"]),
                int(bounds["y"]),
                int(bounds["x"] + bounds["width"]),
                int(bounds["y"] + bounds["height"]),
            )
            ImageGrab.grab(bbox=bbox).save(path)
        except Exception as exc:
            return {"status": "ERROR", "error": f"ImageGrab capture failed: {exc}"}
    else:
        rect = f"{bounds['x']},{bounds['y']},{bounds['width']},{bounds['height']}"
        try:
            proc = subprocess.run(
                ["screencapture", "-x", "-R", rect, str(path)],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "ERROR", "error": "screencapture timed out"}
        if proc.returncode != 0:
            return {"status": "ERROR", "error": proc.stderr.strip() or "capture failed"}
    return {"status": "OK", "screenshot_path": str(path), "bounds": bounds}


def generate_frame_delta_report(run_dir: str | Path) -> dict[str, Any]:
    base = Path(run_dir)
    telemetry = base / "telemetry"
    frames = [
        row for row in _load_jsonl(telemetry / "frames.jsonl")
        if row.get("screenshot_path") and not row.get("dropped")
    ]
    deltas_path = telemetry / "frame_deltas.jsonl"
    interesting_path = telemetry / "interesting_frames.md"
    contact_path = telemetry / "contact_sheet.png"
    if Image is None or ImageChops is None or ImageStat is None:
        interesting_path.write_text(
            "# Interesting Frames\n\nPillow is unavailable; no image diff report generated.\n",
            encoding="utf-8",
        )
        return {"status": "SKIPPED", "reason": "pillow_unavailable"}

    previous = None
    deltas: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        path = Path(str(frame["screenshot_path"]))
        if not path.exists():
            continue
        with Image.open(path) as img:
            cur = img.convert("L").resize((160, 94))
        score = 0.0
        if previous is not None:
            diff = ImageChops.difference(previous, cur)
            score = float(ImageStat.Stat(diff).mean[0])
        row = {
            "index": index,
            "screenshot_path": str(path),
            "delta_score": round(score, 3),
            "interesting": score >= 12.0 or index == 0,
        }
        deltas.append(row)
        if row["interesting"]:
            selected.append(row)
        previous = cur

    with deltas_path.open("w", encoding="utf-8") as fh:
        for row in deltas:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    _write_interesting_markdown(interesting_path, telemetry, selected)
    _write_contact_sheet(contact_path, selected[:40])
    return {
        "status": "OK",
        "frames": len(frames),
        "interesting": len(selected),
        "frame_deltas_path": str(deltas_path),
        "interesting_frames_path": str(interesting_path),
        "contact_sheet_path": str(contact_path),
    }


def _write_interesting_markdown(path: Path, telemetry_dir: Path, rows: list[dict[str, Any]]) -> None:
    lines = ["# Interesting Frames", ""]
    if not rows:
        lines.append("No large frame deltas were detected.")
    for row in rows:
        screenshot = Path(str(row["screenshot_path"]))
        try:
            rel = screenshot.relative_to(telemetry_dir)
        except ValueError:
            rel = screenshot
        lines.append(
            f"- Frame {row['index']}: delta {row['delta_score']} "
            f"[screenshot]({rel})"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    if Image is None or not rows:
        return
    thumbs = []
    for row in rows:
        screenshot = Path(str(row["screenshot_path"]))
        if not screenshot.exists():
            continue
        with Image.open(screenshot) as img:
            thumb = img.convert("RGB")
            thumb.thumbnail((240, 140))
            thumbs.append(thumb.copy())
    if not thumbs:
        return
    cols = 4
    rows_count = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 240, rows_count * 140), (18, 18, 18))
    for i, thumb in enumerate(thumbs):
        x = (i % cols) * 240
        y = (i // cols) * 140
        sheet.paste(thumb, (x, y))
    sheet.save(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
