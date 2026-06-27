"""Telemetry helpers for Lightning War autonomous attempts."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # pragma: no cover - only used on stripped environments
    Image = None
    ImageChops = None
    ImageStat = None


SCHEMA_VERSION = 1
DEFAULT_SCREENSHOT_RUN_CAP = 3


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


def _filename_slug(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower()
    out = []
    for char in text:
        if char.isalnum():
            out.append(char)
        elif char in {"-", "_"}:
            out.append(char)
        elif char in {":", ".", " ", "/"}:
            out.append("-")
    slug = "".join(out).strip("-_")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or default


def _timer_filename_slug(sample: dict[str, Any] | None) -> str | None:
    if not sample:
        return None
    if sample.get("status") != "OK":
        status = _filename_slug(sample.get("status"), default="unavailable")
        return f"gt-{status}"
    timer = sample.get("game_timer")
    if timer:
        return f"gt{_filename_slug(timer, default='unknown')}"
    try:
        seconds = int(round(float(sample.get("game_seconds"))))
    except (TypeError, ValueError):
        return "gt-unknown"
    return f"gt{seconds:06d}s"


def _screenshot_filename(
    *,
    index: int,
    wall_ms: int,
    clock_state: str,
    timer_slug: str | None = None,
) -> str:
    name_parts = [f"{index:06d}", str(wall_ms)]
    if timer_slug:
        name_parts.append(_filename_slug(timer_slug, default="gt-unknown"))
    name_parts.append(_filename_slug(clock_state, default="state"))
    return "_".join(name_parts) + ".png"


def lightning_screenshot_run_cap() -> int | None:
    """Return the cross-run Lightning screenshot retention cap."""
    raw = os.environ.get(
        "ITB_LIGHTNING_SCREENSHOT_RUNS_CAP",
        str(DEFAULT_SCREENSHOT_RUN_CAP),
    ).strip()
    if raw.lower() in {"", "none", "off", "0"}:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_SCREENSHOT_RUN_CAP


def prune_lightning_screenshot_runs(
    *,
    recordings_root: Path | str = Path("recordings"),
    run_notes_root: Path | str = Path("run_notes"),
    max_runs: int | None = None,
) -> dict[str, Any]:
    """Delete screenshot-heavy Lightning artifacts outside the newest runs."""
    cap = lightning_screenshot_run_cap() if max_runs is None else max_runs
    if cap is None:
        return {"status": "SKIPPED", "reason": "retention_disabled", "max_runs": None}
    cap = max(1, int(cap))
    groups = [
        *_recording_screenshot_groups(Path(recordings_root)),
        *_run_note_screenshot_groups(Path(run_notes_root)),
    ]
    groups.sort(key=lambda item: (item["mtime"], item["run_key"]), reverse=True)
    retained_keys: set[str] = set()
    for group in groups:
        if len(retained_keys) >= cap and group["run_key"] not in retained_keys:
            continue
        retained_keys.add(group["run_key"])
    deleted: list[str] = []
    errors: list[dict[str, str]] = []
    for group in groups:
        if group["run_key"] in retained_keys:
            continue
        path = Path(str(group["path"]))
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
            else:
                continue
            deleted.append(str(path))
        except OSError as exc:
            errors.append({"path": str(path), "error": str(exc)})
    status = "OK" if not errors else "PARTIAL"
    return {
        "status": status,
        "max_runs": cap,
        "retained_run_keys": sorted(retained_keys),
        "deleted_count": len(deleted),
        "deleted": deleted,
        "errors": errors,
    }


def _recording_screenshot_groups(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    groups: list[dict[str, Any]] = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        run_key = run_dir.name
        screenshots_dir = run_dir / "telemetry" / "screenshots"
        if _has_png_descendant(screenshots_dir):
            groups.append(_artifact_group(run_key, screenshots_dir))
        telemetry_dir = run_dir / "telemetry"
        if telemetry_dir.exists():
            for child in telemetry_dir.iterdir():
                if child.name == "screenshots" or not child.is_dir():
                    continue
                if _has_png_descendant(child):
                    groups.append(_artifact_group(run_key, child))
            for png in telemetry_dir.glob("*.png"):
                if png.is_file():
                    groups.append(_artifact_group(run_key, png))
        if run_dir.name == "prompt_debug" and _has_png_descendant(run_dir):
            groups.append(_artifact_group(run_key, run_dir))
    return groups


def _run_note_screenshot_groups(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    groups: list[dict[str, Any]] = []
    for note_dir in root.iterdir():
        if note_dir.is_file() and note_dir.suffix.lower() == ".png":
            groups.append(_artifact_group(f"run_notes/{note_dir.stem}", note_dir))
            continue
        if not note_dir.is_dir():
            continue
        if note_dir.name.startswith("research_") and _has_png_descendant(note_dir):
            groups.append(_artifact_group(f"run_notes/{note_dir.name}", note_dir))
            continue
        if not note_dir.name.startswith("lightning_"):
            continue
        for child in note_dir.iterdir():
            if child.is_dir() and _has_png_descendant(child):
                groups.append(_artifact_group(f"{note_dir.name}/{child.name}", child))
            elif child.is_file() and child.suffix.lower() == ".png":
                groups.append(_artifact_group(note_dir.name, child))
    return groups


def _artifact_group(run_key: str, path: Path) -> dict[str, Any]:
    return {"run_key": run_key, "path": path, "mtime": _artifact_mtime(path)}


def _artifact_mtime(path: Path) -> float:
    try:
        if path.is_file():
            return path.stat().st_mtime
        newest = path.stat().st_mtime
        for child in path.rglob("*"):
            try:
                newest = max(newest, child.stat().st_mtime)
            except OSError:
                continue
        return newest
    except OSError:
        return 0.0


def _has_png_descendant(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        if path.is_file():
            return path.suffix.lower() == ".png"
        return any(child.is_file() for child in path.rglob("*.png"))
    except OSError:
        return False


def _clock_frame_fields(sample: dict[str, Any] | None) -> dict[str, Any]:
    if not sample:
        return {}
    keys = (
        "status",
        "clock_source",
        "game_timer",
        "game_seconds",
        "game_timer_ms",
        "timer_validation",
        "pid",
        "address",
        "raw",
        "reason",
    )
    compact = {
        key: sample.get(key)
        for key in keys
        if sample.get(key) is not None
    }
    return {
        "frame_clock_status": sample.get("status"),
        "frame_clock": compact,
        **{
            key: sample.get(key)
            for key in (
                "clock_source",
                "game_timer",
                "game_seconds",
                "game_timer_ms",
            )
            if sample.get(key) is not None
        },
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
        run_notes_root = (
            Path("run_notes")
            if self.root == Path("recordings")
            else self.root.parent / "run_notes"
        )
        self.retention_result = prune_lightning_screenshot_runs(
            recordings_root=self.root,
            run_notes_root=run_notes_root,
        )

    def write_manifest(self, payload: dict[str, Any]) -> None:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": _now_iso(),
            "code_version": code_version(),
            "screenshot_retention": self.retention_result,
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

    def progress_ledger(self, **payload: Any) -> dict[str, Any]:
        """Record one achievement-progress burst and its timer cost."""
        return self.event("progress_ledger", **payload)

    def timer_hygiene(self, **payload: Any) -> dict[str, Any]:
        """Record speed-run timer cost for one autonomous command burst."""
        return self.event("timer_hygiene", **payload)

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
        progress_rows = [
            event for event in events
            if event.get("event_type") == "progress_ledger"
        ]
        hygiene_rows = [
            event for event in events
            if event.get("event_type") == "timer_hygiene"
        ]
        progress_counts: dict[str, int] = {}
        progress_timer: dict[str, float] = {}
        for event in progress_rows:
            result = str(event.get("result") or "unknown")
            progress_counts[result] = progress_counts.get(result, 0) + 1
            try:
                delta = float(event.get("timer_delta_seconds"))
            except (TypeError, ValueError):
                continue
            if delta > 0:
                progress_timer[result] = progress_timer.get(result, 0.0) + delta
        hygiene_counts: dict[str, int] = {}
        hygiene_timer: dict[str, float] = {}
        for event in hygiene_rows:
            classification = str(event.get("classification") or "unknown")
            hygiene_counts[classification] = hygiene_counts.get(classification, 0) + 1
            try:
                delta = float(event.get("timer_delta_seconds"))
            except (TypeError, ValueError):
                continue
            if delta > 0:
                hygiene_timer[classification] = (
                    hygiene_timer.get(classification, 0.0) + delta
                )
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
            f"- Progress ledger events: {len(progress_rows)}",
            f"- Timer hygiene events: {len(hygiene_rows)}",
        ]
        if progress_counts:
            counts = ", ".join(
                f"{key}={value}" for key, value in sorted(progress_counts.items())
            )
            lines.append(f"- Progress results: {counts}")
        if progress_timer:
            timers_text = ", ".join(
                f"{key}={round(value, 3)}s"
                for key, value in sorted(progress_timer.items())
            )
            lines.append(f"- Positive timer by result: {timers_text}")
        if hygiene_counts:
            counts = ", ".join(
                f"{key}={value}" for key, value in sorted(hygiene_counts.items())
            )
            lines.append(f"- Timer hygiene classes: {counts}")
        if hygiene_timer:
            timers_text = ", ".join(
                f"{key}={round(value, 3)}s"
                for key, value in sorted(hygiene_timer.items())
            )
            lines.append(f"- Positive timer by hygiene class: {timers_text}")
        if extra:
            lines.append("- Extra:")
            for key, value in sorted(extra.items()):
                lines.append(f"  - {key}: {value}")
        self.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ScreenshotRecorder:
    """Best-effort sampler with bounded screenshot retention."""

    def __init__(
        self,
        telemetry: TelemetryRecorder,
        *,
        cadence_seconds: float = 2.0,
        max_retained_frames: int | None = 360,
        max_retained_clock_states: int | None = 3,
        frame_clock_sampler: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self.telemetry = telemetry
        self.cadence_seconds = max(0.5, float(cadence_seconds))
        self.max_retained_frames = (
            None
            if max_retained_frames is None
            else max(1, int(max_retained_frames))
        )
        self.max_retained_clock_states = (
            None
            if max_retained_clock_states is None
            else max(1, int(max_retained_clock_states))
        )
        self._stop = threading.Event()
        self._capture_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._index = 0
        self.frame_clock_sampler = frame_clock_sampler

    def set_cadence(self, cadence_seconds: float) -> None:
        self.cadence_seconds = max(0.5, float(cadence_seconds))

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="lightning-screens", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.cadence_seconds + 1.0))
        self.close()

    def close(self) -> None:
        close = getattr(self.frame_clock_sampler, "close", None)
        if callable(close):
            close()

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
            clock_sample, clock_sample_latency = self._sample_frame_clock()
            timer_slug = _timer_filename_slug(clock_sample)
            wall_ms = int(time.time() * 1000)
            name = _screenshot_filename(
                index=self._index,
                wall_ms=wall_ms,
                clock_state=clock_state,
                timer_slug=timer_slug,
            )
            path = self.telemetry.screenshots_dir / name
            started = time.monotonic()
            result = capture_game_window(path)
            latency = round(time.monotonic() - started, 3)
            if result.get("status") != "OK":
                return self.telemetry.frame(
                    dropped=True,
                    drop_reason=result.get("error") or result.get("reason") or "capture_failed",
                    capture_latency_seconds=latency,
                    clock_sample_latency_seconds=clock_sample_latency,
                    clock_state=clock_state,
                    note=note,
                    **_clock_frame_fields(clock_sample),
                )
            row = self.telemetry.frame(
                dropped=False,
                screenshot_path=str(path),
                capture_latency_seconds=latency,
                clock_sample_latency_seconds=clock_sample_latency,
                clock_state=clock_state,
                note=note,
                bounds=result.get("bounds"),
                **_clock_frame_fields(clock_sample),
            )
            self._prune_retained_screenshots()
            return row
        finally:
            self._capture_lock.release()

    def _sample_frame_clock(self) -> tuple[dict[str, Any] | None, float | None]:
        if self.frame_clock_sampler is None:
            return None, None
        started = time.monotonic()
        try:
            sample = self.frame_clock_sampler()
        except Exception as exc:
            sample = {
                "status": "ERROR",
                "reason": str(exc),
                "clock_source": "frame_clock_sampler",
            }
        return sample, round(time.monotonic() - started, 3)

    def _prune_retained_screenshots(self) -> None:
        self._prune_retained_clock_states()
        self._prune_retained_frames()

    def _prune_retained_clock_states(self) -> None:
        if self.max_retained_clock_states is None:
            return
        rows = [
            row for row in _load_jsonl(self.telemetry.frames_path)
            if row.get("screenshot_path") and not row.get("dropped")
        ]
        ordered_states: list[str] = []
        for row in rows:
            clock_state = str(row.get("clock_state") or "unknown")
            if clock_state not in ordered_states:
                ordered_states.append(clock_state)
        retained_states = set(ordered_states[-self.max_retained_clock_states:])
        if len(ordered_states) <= len(retained_states):
            return
        screenshots_dir = self.telemetry.screenshots_dir.resolve()
        for row in rows:
            clock_state = str(row.get("clock_state") or "unknown")
            if clock_state in retained_states:
                continue
            path = Path(str(row["screenshot_path"]))
            try:
                if path.resolve().parent != screenshots_dir or not path.is_file():
                    continue
                path.unlink()
            except OSError:
                continue

    def _prune_retained_frames(self) -> None:
        if self.max_retained_frames is None:
            return
        screenshots_dir = self.telemetry.screenshots_dir
        try:
            screenshots = [
                path
                for path in screenshots_dir.glob("*.png")
                if path.is_file()
            ]
        except OSError:
            return
        excess = len(screenshots) - self.max_retained_frames
        if excess <= 0:
            return
        sortable = []
        for path in screenshots:
            try:
                sortable.append((path.stat().st_mtime, path.name, path))
            except OSError:
                continue
        sortable.sort()
        for _mtime, _name, path in sortable[:excess]:
            try:
                path.unlink()
            except OSError:
                continue


def capture_game_window(path: Path) -> dict[str, Any]:
    try:
        from src.control.mac_click import _get_window_bounds
        from src.capture.window import take_screenshot
    except Exception as exc:
        return {"status": "ERROR", "error": f"window bounds import failed: {exc}"}
    bounds = _get_window_bounds("Into the Breach")
    if bounds is None:
        return {"status": "ERROR", "error": "could not read Into the Breach window bounds"}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        take_screenshot(path, bounds=bounds)
    except Exception as exc:
        return {"status": "ERROR", "error": f"window capture failed: {exc}"}
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
