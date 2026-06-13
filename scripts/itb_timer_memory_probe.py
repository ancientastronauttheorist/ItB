"""Windows Into the Breach in-memory timer probe.

This intentionally avoids hard-coding a single pointer path. The timer address
can move across process launches, so the resolver first searches for plausible
timer values, validates whether they move with wall time, and only then reports
candidate addresses/pointer roots as evidence.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import re
import struct
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ctypes import wintypes


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
DEFAULT_MAX_VISIBLE_TIMER_SECONDS = 30 * 60


@dataclass(frozen=True)
class NumericTimerKind:
    name: str
    width: int
    alignment: int
    family: str
    scale: float = 1.0
    signed: bool = False


NUMERIC_TIMER_KINDS: tuple[NumericTimerKind, ...] = (
    NumericTimerKind("f32_seconds", 4, 4, "f32"),
    NumericTimerKind("f32_milliseconds", 4, 4, "f32", scale=1000.0),
    NumericTimerKind("f32_frames_60hz", 4, 4, "f32", scale=60.0),
    NumericTimerKind("f64_seconds", 8, 8, "f64"),
    NumericTimerKind("f64_milliseconds", 8, 8, "f64", scale=1000.0),
    NumericTimerKind("f64_frames_60hz", 8, 8, "f64", scale=60.0),
    NumericTimerKind("u32_seconds", 4, 4, "int", signed=False),
    NumericTimerKind("i32_seconds", 4, 4, "int", signed=True),
    NumericTimerKind("u64_seconds", 8, 8, "int", signed=False),
    NumericTimerKind("i64_seconds", 8, 8, "int", signed=True),
    NumericTimerKind("u32_centiseconds", 4, 4, "int", scale=100.0, signed=False),
    NumericTimerKind("i32_centiseconds", 4, 4, "int", scale=100.0, signed=True),
    NumericTimerKind("u64_centiseconds", 8, 8, "int", scale=100.0, signed=False),
    NumericTimerKind("i64_centiseconds", 8, 8, "int", scale=100.0, signed=True),
    NumericTimerKind("u32_milliseconds", 4, 4, "int", scale=1000.0, signed=False),
    NumericTimerKind("i32_milliseconds", 4, 4, "int", scale=1000.0, signed=True),
    NumericTimerKind("u64_milliseconds", 8, 8, "int", scale=1000.0, signed=False),
    NumericTimerKind("i64_milliseconds", 8, 8, "int", scale=1000.0, signed=True),
    NumericTimerKind("u32_frames_60hz", 4, 4, "int", scale=60.0, signed=False),
    NumericTimerKind("i32_frames_60hz", 4, 4, "int", scale=60.0, signed=True),
    NumericTimerKind("u64_frames_60hz", 8, 8, "int", scale=60.0, signed=False),
    NumericTimerKind("i64_frames_60hz", 8, 8, "int", scale=60.0, signed=True),
)
NUMERIC_TIMER_KIND_BY_NAME = {kind.name: kind for kind in NUMERIC_TIMER_KINDS}


@dataclass
class ModuleInfo:
    base: int
    size: int
    path: str


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


class WindowsProcessReader:
    def __init__(self, pid: int) -> None:
        if not hasattr(ctypes, "WinDLL"):
            raise RuntimeError("Windows process memory probing requires Windows")
        self.pid = pid
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._bind()
        self.handle = self.kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            False,
            pid,
        )
        if not self.handle:
            raise OSError(ctypes.get_last_error(), f"OpenProcess failed for {pid}")

    def _bind(self) -> None:
        k = self.kernel32
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.VirtualQueryEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.POINTER(MEMORY_BASIC_INFORMATION),
            ctypes.c_size_t,
        ]
        k.VirtualQueryEx.restype = ctypes.c_size_t
        k.ReadProcessMemory.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k.ReadProcessMemory.restype = wintypes.BOOL
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.Module32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
        k.Module32First.restype = wintypes.BOOL
        k.Module32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
        k.Module32Next.restype = wintypes.BOOL

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "WindowsProcessReader":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def read(self, address: int, size: int) -> bytes | None:
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = self.kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            buf,
            size,
            ctypes.byref(read),
        )
        if not ok or int(read.value) != size:
            return None
        return buf.raw[:size]

    def regions(self, *, max_region_size: int) -> list[tuple[int, int, int]]:
        mbi = MEMORY_BASIC_INFORMATION()
        mbi_size = ctypes.sizeof(mbi)
        address = 0
        out: list[tuple[int, int, int]] = []
        while self.kernel32.VirtualQueryEx(
            self.handle,
            ctypes.c_void_p(address),
            ctypes.byref(mbi),
            mbi_size,
        ):
            base = int(mbi.BaseAddress or 0)
            size = int(mbi.RegionSize or 0)
            next_address = base + max(size, 0x1000)
            protect = int(mbi.Protect)
            if (
                int(mbi.State) == MEM_COMMIT
                and _is_readable_protection(protect)
                and 0 < size <= max_region_size
            ):
                out.append((base, size, protect))
            if next_address <= address:
                break
            address = next_address
        return out

    def module(self, name: str = "Breach.exe") -> ModuleInfo | None:
        snap = self.kernel32.CreateToolhelp32Snapshot(0x00000008 | 0x00000010, self.pid)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return None
        try:
            entry = MODULEENTRY32()
            entry.dwSize = ctypes.sizeof(entry)
            ok = self.kernel32.Module32First(snap, ctypes.byref(entry))
            while ok:
                mod_name = entry.szModule.decode("mbcs", "replace")
                if mod_name.lower() == name.lower():
                    base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                    return ModuleInfo(
                        base=int(base or 0),
                        size=int(entry.modBaseSize),
                        path=entry.szExePath.decode("mbcs", "replace"),
                    )
                ok = self.kernel32.Module32Next(snap, ctypes.byref(entry))
        finally:
            self.kernel32.CloseHandle(snap)
        return None


def _is_readable_protection(protect: int) -> bool:
    if protect & PAGE_GUARD or protect & PAGE_NOACCESS:
        return False
    return bool(protect & (0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80))


def _find_breach_pid() -> int | None:
    try:
        import subprocess

        script = (
            "Get-Process Breach -ErrorAction SilentlyContinue | "
            "Sort-Object StartTime -Descending | Select-Object -First 1 -ExpandProperty Id"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    text = result.stdout.strip()
    return int(text) if text.isdigit() else None


def _format_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _parse_timer_label(label: str) -> float | None:
    parts = label.strip().split(":")
    if len(parts) == 2:
        m, s = parts
        h = "0"
    elif len(parts) == 3:
        h, m, s = parts
    else:
        return None
    if not (h.isdigit() and m.isdigit() and s.isdigit()):
        return None
    minutes = int(m)
    seconds = int(s)
    if minutes >= 60 or seconds >= 60:
        return None
    return float(int(h) * 3600 + minutes * 60 + seconds)


def _parse_timer_words(label: str) -> float | None:
    match = re.fullmatch(r"\s*(\d{1,2})h\s+(\d{1,2})m\s+(\d{1,2})s\s*", label)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    if minutes >= 60 or seconds >= 60:
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def _parse_int_auto(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer/address: {value}") from exc


_DATE_WORD_RE = re.compile(
    r"\b(mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
    re.IGNORECASE,
)


def _looks_like_wall_clock_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 32): min(len(text), end + 40)]
    has_date_word = bool(_DATE_WORD_RE.search(window))
    has_clock_marker = bool(re.search(r"\b(utc|gmt|20\d{2})\b", window, re.IGNORECASE))
    return has_date_word and has_clock_marker


def _extract_context_timers(text: str) -> list[dict[str, Any]]:
    timers: list[dict[str, Any]] = []
    for match in re.finditer(r'\["time"\]\s*=\s*(-?\d+(?:\.\d+)?)', text):
        raw = float(match.group(1))
        if raw >= 0:
            timers.append({
                "source": "GameData.current.time",
                "raw": raw,
                "seconds": raw / 1000.0,
                "game_timer": _format_seconds(raw / 1000.0),
            })
    for match in re.finditer(r"(?<!\d)(\d{1,2}:\d{2}:\d{2})(?!\d)", text):
        if _looks_like_wall_clock_context(text, match.start(), match.end()):
            continue
        seconds = _parse_timer_label(match.group(1))
        if seconds is not None:
            timers.append({
                "source": "visible_timer_string",
                "raw": match.group(1),
                "seconds": seconds,
                "game_timer": _format_seconds(seconds),
                "text_offset": match.start(1),
            })
    for match in re.finditer(r"(?<!\d)(\d{1,2}h\s+\d{1,2}m\s+\d{1,2}s)", text):
        seconds = _parse_timer_words(match.group(1))
        if seconds is not None:
            timers.append({
                "source": "visible_timeline_playtime_string",
                "raw": match.group(1),
                "seconds": seconds,
                "game_timer": _format_seconds(seconds),
                "text_offset": match.start(1),
            })
    return timers


def summarize_context_timers(context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = {}
    for item in context:
        seconds = int(round(float(item["seconds"])))
        bucket = buckets.setdefault(
            seconds,
            {
                "seconds": float(seconds),
                "game_timer": _format_seconds(seconds),
                "count": 0,
                "sources": Counter(),
                "raw_values": Counter(),
                "regions": Counter(),
            },
        )
        bucket["count"] += 1
        bucket["sources"][str(item.get("source", "unknown"))] += 1
        bucket["raw_values"][str(item.get("raw", item.get("seconds")))] += 1
        if item.get("region_base"):
            bucket["regions"][str(item["region_base"])] += 1
        if item.get("address"):
            bucket.setdefault("addresses", Counter())[str(item["address"])] += 1

    summary: list[dict[str, Any]] = []
    for bucket in buckets.values():
        summary.append({
            "seconds": bucket["seconds"],
            "game_timer": bucket["game_timer"],
            "count": bucket["count"],
            "sources": dict(bucket["sources"].most_common()),
            "raw_values": dict(bucket["raw_values"].most_common(8)),
            "regions": dict(bucket["regions"].most_common(8)),
            "addresses": dict(bucket.get("addresses", Counter()).most_common(8)),
        })
    summary.sort(key=lambda item: (int(item["count"]), float(item["seconds"])), reverse=True)
    return summary


def select_visible_timer_context(
    context: list[dict[str, Any]],
    *,
    max_visible_seconds: float | None = DEFAULT_MAX_VISIBLE_TIMER_SECONDS,
) -> dict[str, Any] | None:
    visible = filter_visible_timer_context(
        context,
        max_visible_seconds=max_visible_seconds,
    )
    timeline_visible = [
        item for item in visible
        if item.get("source") == "visible_timeline_playtime_string"
    ]
    if timeline_visible:
        visible = timeline_visible
    if not visible:
        return None
    summary = summarize_context_timers(visible)
    return summary[0] if summary else None


def filter_visible_timer_context(
    context: list[dict[str, Any]],
    *,
    max_visible_seconds: float | None = DEFAULT_MAX_VISIBLE_TIMER_SECONDS,
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for item in context:
        if not _is_visible_timer_source(item.get("source")):
            continue
        try:
            seconds = float(item.get("seconds"))
        except (TypeError, ValueError):
            continue
        if max_visible_seconds is not None and seconds > max_visible_seconds:
            continue
        if _looks_like_placeholder_timer(item.get("raw")):
            continue
        visible.append(item)
    return visible


def _is_visible_timer_source(source: Any) -> bool:
    return str(source) in {
        "visible_timer_string",
        "visible_timeline_playtime_string",
    }


def _looks_like_placeholder_timer(raw: Any) -> bool:
    text = str(raw or "").strip()
    colon = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if colon and len({colon.group(1), colon.group(2), colon.group(3)}) == 1:
        return text != "0:00:00"
    words = re.fullmatch(r"(\d{1,2})h\s+(\d{1,2})m\s+(\d{1,2})s", text)
    if words and len({words.group(1), words.group(2), words.group(3)}) == 1:
        return text != "0h 0m 0s"
    return False


def scan_context_timers(
    reader: WindowsProcessReader,
    *,
    max_region_size: int,
    max_hits: int,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    patterns = (b"GameData = ", b'Timeline Playtime', b"Playtime", b"1:")
    for base, size, _protect in reader.regions(max_region_size=max_region_size):
        data = reader.read(base, size)
        if not data:
            continue
        if not any(pattern in data for pattern in patterns):
            continue
        text = data.decode("latin-1")
        for timer in _extract_context_timers(text):
            timer["region_base"] = f"0x{base:016x}"
            if timer.get("text_offset") is not None:
                timer["address"] = f"0x{base + int(timer['text_offset']):016x}"
            hits.append(timer)
            if len(hits) >= max_hits:
                return hits
    return hits


def read_timeline_playtime_address(
    reader: WindowsProcessReader,
    address: int,
    *,
    size: int = 64,
) -> dict[str, Any]:
    data = reader.read(address, size)
    if not data:
        return {
            "status": "ERROR",
            "reason": "address could not be read",
            "address": f"0x{address:016x}",
        }
    text = data.decode("utf-8", "replace")
    leading = re.match(r"\s*(\d{1,2}h\s+\d{1,2}m\s+\d{1,2}s)", text)
    if leading:
        seconds = _parse_timer_words(leading.group(1))
        if seconds is not None:
            return {
                "status": "OK",
                "address": f"0x{address:016x}",
                "raw_text": text,
                "source": "visible_timeline_playtime_string",
                "raw": leading.group(1),
                "seconds": seconds,
                "game_timer": _format_seconds(seconds),
            }
    for timer in _extract_context_timers(text):
        if timer.get("source") != "visible_timeline_playtime_string":
            continue
        if int(timer.get("text_offset") or 0) != 0:
            continue
        timer.pop("text_offset", None)
        return {
            "status": "OK",
            "address": f"0x{address:016x}",
            "raw_text": text,
            **timer,
        }
    return {
        "status": "NO_TIMER",
        "address": f"0x{address:016x}",
        "raw_text": text,
    }


def _score_candidate(
    before: float,
    after: float,
    elapsed: float,
    expected_seconds: float | None,
) -> tuple[float, str]:
    delta = after - before
    if 0.5 <= delta <= elapsed + 1.0:
        return max(0.0, 100.0 - abs(delta - elapsed) * 20.0), "moving"
    if abs(delta) <= 0.005:
        if expected_seconds is not None:
            distance = abs(before - expected_seconds)
            if distance <= 5.0:
                return 75.0 - distance, "paused_expected_match"
        return 20.0, "stable"
    return 0.0, "rejected_delta"


def _is_writable_protection(protect: int) -> bool:
    if protect & PAGE_GUARD or protect & PAGE_NOACCESS:
        return False
    return bool(protect & (0x04 | 0x08 | 0x40 | 0x80))


def _parse_numeric_kinds(raw: str | None) -> tuple[NumericTimerKind, ...]:
    if not raw or raw.strip().lower() in {"all", "*"}:
        return NUMERIC_TIMER_KINDS
    names = [name.strip() for name in raw.split(",") if name.strip()]
    kinds: list[NumericTimerKind] = []
    invalid: list[str] = []
    for name in names:
        kind = NUMERIC_TIMER_KIND_BY_NAME.get(name)
        if kind is None:
            invalid.append(name)
        else:
            kinds.append(kind)
    if invalid:
        valid = ", ".join(sorted(NUMERIC_TIMER_KIND_BY_NAME))
        raise argparse.ArgumentTypeError(
            f"invalid numeric timer kind(s): {', '.join(invalid)}; valid: {valid}"
        )
    return tuple(kinds)


def _json_number(value: float | int) -> float | int:
    if isinstance(value, float):
        return round(value, 6)
    return value


def _decode_numeric_timer(data: bytes, offset: int, kind: NumericTimerKind) -> tuple[float | int, float] | None:
    if offset + kind.width > len(data):
        return None
    try:
        if kind.family == "f32":
            raw: float | int = struct.unpack_from("<f", data, offset)[0]
        elif kind.family == "f64":
            raw = struct.unpack_from("<d", data, offset)[0]
        else:
            raw = int.from_bytes(
                data[offset:offset + kind.width],
                "little",
                signed=kind.signed,
            )
    except struct.error:
        return None
    if isinstance(raw, float):
        if not math.isfinite(raw) or raw < 0:
            return None
    elif raw < 0:
        return None
    seconds = float(raw) / kind.scale
    if not math.isfinite(seconds):
        return None
    return raw, seconds


def _numeric_candidate_key(candidate: dict[str, Any]) -> str:
    return f"{candidate.get('address')}|{candidate.get('kind')}"


def _read_numeric_candidate(
    reader: WindowsProcessReader,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    kind = NUMERIC_TIMER_KIND_BY_NAME.get(str(candidate.get("kind")))
    try:
        address = int(str(candidate.get("address")), 16)
    except (TypeError, ValueError):
        return {
            "address": candidate.get("address"),
            "kind": candidate.get("kind"),
            "read_ok": False,
            "reason": "invalid_address",
        }
    if kind is None:
        return {
            "address": f"0x{address:016x}",
            "kind": candidate.get("kind"),
            "read_ok": False,
            "reason": "invalid_kind",
        }
    data = reader.read(address, kind.width)
    if data is None or len(data) != kind.width:
        return {
            "address": f"0x{address:016x}",
            "kind": kind.name,
            "width": kind.width,
            "read_ok": False,
            "reason": "read_failed",
        }
    decoded = _decode_numeric_timer(data, 0, kind)
    if decoded is None:
        return {
            "address": f"0x{address:016x}",
            "kind": kind.name,
            "width": kind.width,
            "read_ok": False,
            "reason": "decode_failed",
            "bytes": data.hex(),
        }
    raw, seconds = decoded
    return {
        "address": f"0x{address:016x}",
        "kind": kind.name,
        "width": kind.width,
        "read_ok": True,
        "raw_value": _json_number(raw),
        "seconds": round(seconds, 6),
        "game_timer": _format_seconds(seconds),
        "bytes": data.hex(),
    }


def read_numeric_timer_address(
    reader: WindowsProcessReader,
    address: int,
    kind_name: str,
) -> dict[str, Any]:
    return _read_numeric_candidate(
        reader,
        {
            "address": f"0x{address:016x}",
            "kind": kind_name,
        },
    )


def _append_bounded_candidate(
    bucket: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    max_candidates: int,
) -> None:
    if len(bucket) < max_candidates:
        bucket.append(candidate)
        return
    worst_index = max(
        range(len(bucket)),
        key=lambda idx: float(bucket[idx].get("distance_seconds", 0.0)),
    )
    if float(candidate.get("distance_seconds", 0.0)) < float(
        bucket[worst_index].get("distance_seconds", 0.0)
    ):
        bucket[worst_index] = candidate


def scan_numeric_timer_candidates(
    reader: WindowsProcessReader,
    *,
    expected_seconds: float,
    seconds_window: float,
    max_timer_seconds: float,
    max_region_size: int,
    max_candidates_per_kind: int,
    kinds: tuple[NumericTimerKind, ...] = NUMERIC_TIMER_KINDS,
    include_readonly: bool = False,
) -> dict[str, Any]:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - fallback for stripped environments
        np = None

    low = max(0.0, expected_seconds - seconds_window)
    high = min(max_timer_seconds, expected_seconds + seconds_window)
    by_kind: dict[str, list[dict[str, Any]]] = {kind.name: [] for kind in kinds}

    scanned_regions = 0
    scanned_bytes = 0
    skipped_regions = 0
    skipped_reasons: Counter[str] = Counter()
    for base, size, protect in reader.regions(max_region_size=max_region_size):
        if not include_readonly and not _is_writable_protection(protect):
            skipped_regions += 1
            skipped_reasons["readonly"] += 1
            continue
        data = reader.read(base, size)
        if not data:
            skipped_regions += 1
            skipped_reasons["read_failed"] += 1
            continue
        scanned_regions += 1
        scanned_bytes += len(data)
        if np is not None:
            _scan_numeric_region_numpy(
                data,
                base=base,
                protect=protect,
                expected_seconds=expected_seconds,
                low=low,
                high=high,
                kinds=kinds,
                by_kind=by_kind,
                max_candidates_per_kind=max_candidates_per_kind,
                np=np,
            )
        else:
            _scan_numeric_region_python(
                data,
                base=base,
                protect=protect,
                expected_seconds=expected_seconds,
                low=low,
                high=high,
                kinds=kinds,
                by_kind=by_kind,
                max_candidates_per_kind=max_candidates_per_kind,
            )

    candidates: list[dict[str, Any]] = []
    for bucket in by_kind.values():
        bucket.sort(
            key=lambda item: (
                float(item.get("distance_seconds", 0.0)),
                int(str(item.get("address")), 16),
            )
        )
        candidates.extend(bucket)
    candidates.sort(
        key=lambda item: (
            float(item.get("distance_seconds", 0.0)),
            str(item.get("kind")),
            int(str(item.get("address")), 16),
        )
    )
    return {
        "expected_seconds": expected_seconds,
        "expected_timer": _format_seconds(expected_seconds),
        "search_range": [round(low, 6), round(high, 6)],
        "seconds_window": seconds_window,
        "max_timer_seconds": max_timer_seconds,
        "kinds": [kind.name for kind in kinds],
        "include_readonly": include_readonly,
        "scanned_regions": scanned_regions,
        "scanned_bytes": scanned_bytes,
        "skipped_regions": skipped_regions,
        "skipped_reasons": dict(skipped_reasons),
        "candidate_count": len(candidates),
        "candidate_count_by_kind": {
            kind: len(bucket)
            for kind, bucket in sorted(by_kind.items())
            if bucket
        },
        "candidates": candidates,
    }


def _scan_numeric_region_python(
    data: bytes,
    *,
    base: int,
    protect: int,
    expected_seconds: float,
    low: float,
    high: float,
    kinds: tuple[NumericTimerKind, ...],
    by_kind: dict[str, list[dict[str, Any]]],
    max_candidates_per_kind: int,
) -> None:
    kinds_by_width: dict[int, list[NumericTimerKind]] = {}
    for kind in kinds:
        kinds_by_width.setdefault(kind.width, []).append(kind)
    for width, width_kinds in kinds_by_width.items():
        if len(data) < width:
            continue
        alignment = min(kind.alignment for kind in width_kinds)
        for offset in range(0, len(data) - width + 1, alignment):
            for kind in width_kinds:
                if offset % kind.alignment != 0:
                    continue
                decoded = _decode_numeric_timer(data, offset, kind)
                if decoded is None:
                    continue
                raw, seconds = decoded
                if seconds < low or seconds > high:
                    continue
                _append_numeric_candidate(
                    by_kind,
                    base=base,
                    offset=offset,
                    protect=protect,
                    kind=kind,
                    raw=raw,
                    seconds=seconds,
                    expected_seconds=expected_seconds,
                    max_candidates_per_kind=max_candidates_per_kind,
                )


def _scan_numeric_region_numpy(
    data: bytes,
    *,
    base: int,
    protect: int,
    expected_seconds: float,
    low: float,
    high: float,
    kinds: tuple[NumericTimerKind, ...],
    by_kind: dict[str, list[dict[str, Any]]],
    max_candidates_per_kind: int,
    np: Any,
) -> None:
    for kind in kinds:
        width = kind.width
        usable = len(data) - (len(data) % width)
        if usable <= 0:
            continue
        view = memoryview(data)[:usable]
        if kind.family == "f32":
            raw_values = np.frombuffer(view, dtype="<f4")
        elif kind.family == "f64":
            raw_values = np.frombuffer(view, dtype="<f8")
        elif kind.width == 4:
            raw_values = np.frombuffer(view, dtype="<i4" if kind.signed else "<u4")
        elif kind.width == 8:
            raw_values = np.frombuffer(view, dtype="<i8" if kind.signed else "<u8")
        else:
            continue
        seconds = raw_values.astype(np.float64) / float(kind.scale)
        mask = np.isfinite(seconds) & (seconds >= low) & (seconds <= high)
        indexes = np.nonzero(mask)[0]
        if indexes.size == 0:
            continue
        distances = np.abs(seconds[indexes] - float(expected_seconds))
        if indexes.size > max_candidates_per_kind:
            keep = np.argpartition(distances, max_candidates_per_kind - 1)[
                :max_candidates_per_kind
            ]
            indexes = indexes[keep]
            distances = distances[keep]
        order = np.argsort(distances, kind="stable")
        for idx in indexes[order]:
            raw = raw_values[idx].item()
            value = float(seconds[idx])
            _append_numeric_candidate(
                by_kind,
                base=base,
                offset=int(idx) * width,
                protect=protect,
                kind=kind,
                raw=raw,
                seconds=value,
                expected_seconds=expected_seconds,
                max_candidates_per_kind=max_candidates_per_kind,
            )


def _append_numeric_candidate(
    by_kind: dict[str, list[dict[str, Any]]],
    *,
    base: int,
    offset: int,
    protect: int,
    kind: NumericTimerKind,
    raw: float | int,
    seconds: float,
    expected_seconds: float,
    max_candidates_per_kind: int,
) -> None:
    candidate = {
        "address": f"0x{base + offset:016x}",
        "region_base": f"0x{base:016x}",
        "offset": offset,
        "protect": f"0x{protect:x}",
        "kind": kind.name,
        "width": kind.width,
        "raw_value": _json_number(raw),
        "seconds": round(seconds, 6),
        "game_timer": _format_seconds(seconds),
        "distance_seconds": round(abs(seconds - expected_seconds), 6),
    }
    _append_bounded_candidate(
        by_kind[kind.name],
        candidate,
        max_candidates=max_candidates_per_kind,
    )


def summarize_numeric_scan_for_console(payload: dict[str, Any], output_path: str | None) -> dict[str, Any]:
    scan = payload["numeric_scan"]
    summary = {
        "status": payload["status"],
        "pid": payload["pid"],
        "expected_timer": scan["expected_timer"],
        "expected_seconds": scan["expected_seconds"],
        "search_range": scan["search_range"],
        "scanned_regions": scan["scanned_regions"],
        "scanned_bytes": scan["scanned_bytes"],
        "candidate_count": scan["candidate_count"],
        "candidate_count_by_kind": scan["candidate_count_by_kind"],
        "top_candidates": scan["candidates"][:20],
        "notes": payload["notes"],
    }
    if output_path:
        summary["output"] = output_path
    return summary


def _candidate_tracks(
    reader: WindowsProcessReader,
    candidates: list[dict[str, Any]],
    *,
    samples: int,
    interval_seconds: float,
) -> dict[str, Any]:
    samples_out: list[dict[str, Any]] = []
    tracks: dict[str, dict[str, Any]] = {
        _numeric_candidate_key(candidate): {
            "candidate": candidate,
            "seconds": [],
            "raw_values": [],
            "read_ok": [],
        }
        for candidate in candidates
    }
    started = time.monotonic()
    for idx in range(samples):
        now = time.monotonic()
        elapsed = round(now - started, 6)
        sample_info = {
            "index": idx,
            "elapsed_seconds": elapsed,
            "created_at": time.time(),
        }
        for candidate in candidates:
            key = _numeric_candidate_key(candidate)
            value = _read_numeric_candidate(reader, candidate)
            ok = bool(value.get("read_ok"))
            tracks[key]["read_ok"].append(ok)
            tracks[key]["seconds"].append(value.get("seconds") if ok else None)
            tracks[key]["raw_values"].append(value.get("raw_value") if ok else None)
        samples_out.append(sample_info)
        if idx + 1 < samples:
            target = started + (idx + 1) * max(0.05, interval_seconds)
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)

    elapsed_total = (
        float(samples_out[-1]["elapsed_seconds"])
        if samples_out
        else 0.0
    )
    track_rows: list[dict[str, Any]] = []
    for track in tracks.values():
        values = [
            float(value)
            for value in track["seconds"]
            if value is not None
        ]
        if len(values) < 2:
            continue
        delta = values[-1] - values[0]
        monotonic = all(
            values[idx + 1] >= values[idx] - 0.05
            for idx in range(len(values) - 1)
        )
        live_delta_error = abs(delta - elapsed_total)
        track_rows.append({
            "candidate": track["candidate"],
            "read_count": len(values),
            "sample_count": samples,
            "seconds": track["seconds"],
            "raw_values": track["raw_values"],
            "first_seconds": round(values[0], 6),
            "last_seconds": round(values[-1], 6),
            "delta_seconds": round(delta, 6),
            "elapsed_seconds": round(elapsed_total, 6),
            "live_delta_error_seconds": round(live_delta_error, 6),
            "monotonic": monotonic,
            "moving_like_timer": bool(monotonic and live_delta_error <= 1.0 and delta >= 0.5),
        })
    track_rows.sort(
        key=lambda item: (
            not bool(item["moving_like_timer"]),
            float(item["live_delta_error_seconds"]),
            float(item["candidate"].get("distance_seconds", 0.0)),
            int(str(item["candidate"].get("address")), 16),
        )
    )
    return {
        "samples": samples_out,
        "elapsed_seconds": round(elapsed_total, 6),
        "tracks": track_rows,
        "track_count": len(track_rows),
    }


def _score_numeric_tracks(
    *,
    tracks: list[dict[str, Any]],
    start_truth_seconds: float | None,
    final_truth_seconds: float | None,
    current_values: dict[str, dict[str, Any]],
    stable_values: dict[str, dict[str, Any]],
    max_results: int,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for track in tracks:
        candidate = track.get("candidate") or {}
        key = _numeric_candidate_key(candidate)
        current = current_values.get(key)
        stable = stable_values.get(key)
        if not current or not current.get("read_ok"):
            continue
        current_seconds = float(current["seconds"])
        stable_seconds = (
            float(stable["seconds"])
            if stable and stable.get("read_ok")
            else current_seconds
        )
        start_error = (
            abs(float(track["first_seconds"]) - start_truth_seconds)
            if start_truth_seconds is not None
            else None
        )
        final_error = (
            abs(current_seconds - final_truth_seconds)
            if final_truth_seconds is not None
            else None
        )
        pause_delta = abs(stable_seconds - current_seconds)
        live_delta_error = float(track.get("live_delta_error_seconds") or 999.0)
        score = 100.0
        score -= min(40.0, live_delta_error * 20.0)
        if start_error is not None:
            score -= min(30.0, start_error * 10.0)
        if final_error is not None:
            score -= min(30.0, final_error * 10.0)
        score -= min(20.0, pause_delta * 25.0)
        if not track.get("monotonic"):
            score -= 25.0
        if not track.get("moving_like_timer"):
            score -= 30.0
        status = "candidate"
        if (
            track.get("moving_like_timer")
            and (start_error is None or start_error <= 2.0)
            and (final_error is None or final_error <= 2.0)
            and pause_delta <= 0.25
        ):
            status = "validated_cycle_candidate"
        elif start_error is not None and start_error > 5.0:
            status = "moving_wrong_start_value"
        elif final_error is not None and final_error > 5.0:
            status = "moving_wrong_final_value"
        elif pause_delta > 0.5:
            status = "still_moving_while_paused"
        scored.append({
            "status": status,
            "score": round(score, 3),
            "candidate": candidate,
            "first_seconds": track.get("first_seconds"),
            "last_live_seconds": track.get("last_seconds"),
            "current_seconds": round(current_seconds, 6),
            "stable_seconds": round(stable_seconds, 6),
            "game_timer": _format_seconds(current_seconds),
            "live_delta_seconds": track.get("delta_seconds"),
            "live_elapsed_seconds": track.get("elapsed_seconds"),
            "live_delta_error_seconds": track.get("live_delta_error_seconds"),
            "start_error_seconds": (
                round(start_error, 6)
                if start_error is not None
                else None
            ),
            "final_error_seconds": (
                round(final_error, 6)
                if final_error is not None
                else None
            ),
            "paused_delta_seconds": round(pause_delta, 6),
            "monotonic": track.get("monotonic"),
            "samples": track.get("seconds"),
        })
    scored.sort(
        key=lambda item: (
            item["status"] != "validated_cycle_candidate",
            -float(item["score"]),
            float(item["final_error_seconds"] or 0.0),
            float(item["live_delta_error_seconds"] or 0.0),
            int(str(item["candidate"].get("address")), 16),
        )
    )
    return scored[:max_results]


def scan_f32_candidates(
    reader: WindowsProcessReader,
    *,
    expected_seconds: float | None,
    sample_seconds: float,
    max_region_size: int,
    max_candidates: int,
    max_results: int,
) -> dict[str, Any]:
    if expected_seconds is None:
        low, high = 0.0, 30 * 3600.0
    else:
        low = max(0.0, expected_seconds - 20.0)
        high = expected_seconds + 20.0

    first: list[tuple[int, float]] = []
    scanned_regions = 0
    scanned_bytes = 0
    for base, size, _protect in reader.regions(max_region_size=max_region_size):
        data = reader.read(base, size)
        if not data:
            continue
        scanned_regions += 1
        scanned_bytes += len(data)
        for offset in range(0, len(data) - 4, 4):
            value = struct.unpack_from("<f", data, offset)[0]
            if low <= value <= high and math.isfinite(value):
                first.append((base + offset, value))
                if len(first) >= max_candidates:
                    break
        if len(first) >= max_candidates:
            break

    time.sleep(sample_seconds)
    elapsed = sample_seconds
    results: list[dict[str, Any]] = []
    for address, before in first:
        data = reader.read(address, 4)
        if not data:
            continue
        after = struct.unpack("<f", data)[0]
        score, status = _score_candidate(before, after, elapsed, expected_seconds)
        if score <= 0:
            continue
        results.append({
            "address": f"0x{address:016x}",
            "before": before,
            "after": after,
            "delta": after - before,
            "status": status,
            "score": round(score, 3),
            "game_timer": _format_seconds(after),
        })
    results.sort(key=lambda item: float(item["score"]), reverse=True)
    return {
        "expected_seconds": expected_seconds,
        "search_range": [low, high],
        "scanned_regions": scanned_regions,
        "scanned_bytes": scanned_bytes,
        "candidate_count": len(first),
        "results": results[:max_results],
    }


def discover_pointer_roots(
    reader: WindowsProcessReader,
    module: ModuleInfo,
    target_address: int,
    *,
    max_field_offset: int,
    max_roots: int,
) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    start = module.base
    end = module.base + module.size
    data = reader.read(start, module.size)
    if not data:
        return roots
    for offset in range(0, len(data) - 4, 4):
        pointer = int.from_bytes(data[offset:offset + 4], "little")
        field_offset = target_address - pointer
        if 0 <= field_offset <= max_field_offset:
            roots.append({
                "root": f"0x{start + offset:016x}",
                "module_offset": f"0x{offset:x}",
                "pointer": f"0x{pointer:016x}",
                "field_offset": f"0x{field_offset:x}",
            })
            if len(roots) >= max_roots:
                break
    return roots


def summarize_payload_for_console(payload: dict[str, Any], output_path: str | None) -> dict[str, Any]:
    f32 = payload["f32_scan"]
    summary = {
        "status": payload["status"],
        "pid": payload["pid"],
        "module": payload["module"],
        "expected_selection": payload["expected_selection"],
        "expected_seconds": payload["expected_seconds"],
        "expected_timer": payload["expected_timer"],
        "context_summary_top": payload["context_summary"][:10],
        "f32_scan": {
            "expected_seconds": f32["expected_seconds"],
            "search_range": f32["search_range"],
            "scanned_regions": f32["scanned_regions"],
            "scanned_bytes": f32["scanned_bytes"],
            "candidate_count": f32["candidate_count"],
            "results": f32["results"],
        },
        "pointer_roots": payload["pointer_roots"][:10],
        "notes": payload["notes"],
    }
    if output_path:
        summary["output"] = output_path
    return summary


def resolve_expected_seconds(
    args: argparse.Namespace,
    context: list[dict[str, Any]],
) -> tuple[float | None, dict[str, Any]]:
    if args.expected_seconds is not None:
        seconds = float(args.expected_seconds)
        return seconds, {
            "strategy": "explicit_seconds",
            "seconds": seconds,
            "game_timer": _format_seconds(seconds),
        }
    if args.expected_timer:
        seconds = _parse_timer_label(args.expected_timer)
        return seconds, {
            "strategy": "explicit_timer",
            "raw": args.expected_timer,
            "seconds": seconds,
            "game_timer": _format_seconds(seconds) if seconds is not None else None,
        }
    if context:
        if args.expected_selection == "max":
            best = max(context, key=lambda item: float(item["seconds"]))
            seconds = float(best["seconds"])
            return seconds, {
                "strategy": "max_context",
                "source": best.get("source"),
                "raw": best.get("raw"),
                "seconds": seconds,
                "game_timer": _format_seconds(seconds),
                "reason": "selected the largest observed timer-like context value",
            }

        visible = filter_visible_timer_context(
            context,
            max_visible_seconds=args.max_visible_timer_seconds,
        )
        best = select_visible_timer_context(
            context,
            max_visible_seconds=args.max_visible_timer_seconds,
        )
        summary = [best] if best else summarize_context_timers(context)
        if summary:
            best = summary[0]
            seconds = float(best["seconds"])
            return seconds, {
                "strategy": "mode_context",
                "source_filter": "plausible_visible_timer" if visible else "all_context",
                "seconds": seconds,
                "game_timer": best["game_timer"],
                "count": best["count"],
                "sources": best["sources"],
                "reason": "selected the most frequently repeated rounded timer context value",
            }
    return None, {
        "strategy": "none",
        "reason": "no explicit timer and no timer-like context values were found",
    }


def cmd_scan(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        context = scan_context_timers(
            reader,
            max_region_size=args.max_region_size,
            max_hits=args.max_context_hits,
        )
        context_summary = summarize_context_timers(context)
        expected, expected_selection = resolve_expected_seconds(args, context)
        f32 = scan_f32_candidates(
            reader,
            expected_seconds=expected,
            sample_seconds=args.sample_seconds,
            max_region_size=args.max_region_size,
            max_candidates=args.max_candidates,
            max_results=args.max_results,
        )
        pointer_roots: list[dict[str, Any]] = []
        if module and f32["results"]:
            top_addr = int(str(f32["results"][0]["address"]), 16)
            pointer_roots = discover_pointer_roots(
                reader,
                module,
                top_addr,
                max_field_offset=args.max_field_offset,
                max_roots=args.max_pointer_roots,
            )

    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "context_timers": context[:args.max_context_hits],
        "context_summary": context_summary,
        "expected_selection": expected_selection,
        "expected_seconds": expected,
        "expected_timer": _format_seconds(expected) if expected is not None else None,
        "f32_scan": f32,
        "pointer_roots": pointer_roots,
        "notes": [
            "Moving f32 candidates are preferred when the game is unpaused.",
            "Stable candidates near the expected timer are useful while paused, but lower confidence.",
            "Pointer roots are process-specific hints and must be revalidated after restart.",
        ],
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    console_payload = (
        payload if args.full_output else summarize_payload_for_console(payload, output_path)
    )
    print(json.dumps(console_payload, indent=2))
    return 0


def cmd_read_address(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        payload = read_timeline_playtime_address(
            reader,
            args.address,
            size=args.bytes,
        )
    payload["pid"] = pid
    payload["module"] = module.__dict__ if module else None
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("status") == "OK" else 1


def cmd_read_numeric(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        payload = read_numeric_timer_address(reader, args.address, args.kind)
    payload.update({
        "pid": pid,
        "module": module.__dict__ if module else None,
        "clock_source": "memory_live_numeric_candidate",
        "timer_validation": "direct_numeric_candidate_read",
    })
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("read_ok") else 1


def cmd_watch_context(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2

    samples: list[dict[str, Any]] = []
    for idx in range(args.samples):
        with WindowsProcessReader(pid) as reader:
            module = reader.module()
            context = scan_context_timers(
                reader,
                max_region_size=args.max_region_size,
                max_hits=args.max_context_hits,
            )
        top = select_visible_timer_context(
            context,
            max_visible_seconds=args.max_visible_timer_seconds,
        )
        samples.append({
            "index": idx,
            "created_at": time.time(),
            "context_count": len(context),
            "top_visible_timer": top,
            "context_summary_top": summarize_context_timers(context)[:args.max_summary],
        })
        if idx + 1 < args.samples:
            time.sleep(args.sample_seconds)

    first = samples[0]["top_visible_timer"] if samples else None
    last = samples[-1]["top_visible_timer"] if samples else None
    delta = None
    state = "unknown"
    if first and last:
        delta = float(last["seconds"]) - float(first["seconds"])
        state = "moving" if delta >= args.movement_threshold else "stable"

    payload = {
        "status": "OK",
        "pid": pid,
        "module": module.__dict__ if module else None,
        "sample_seconds": args.sample_seconds,
        "samples": samples,
        "delta_seconds": delta,
        "movement_threshold": args.movement_threshold,
        "timer_state": state,
        "interpretation": (
            "visible timer moved; pause menu is likely closed"
            if state == "moving"
            else "visible timer did not move; pause menu is likely open"
            if state == "stable"
            else "could not infer pause state from visible timer context"
        ),
    }
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


def _resolve_numeric_expected_seconds(
    args: argparse.Namespace,
    reader: WindowsProcessReader,
) -> tuple[float | None, dict[str, Any]]:
    if args.expected_seconds is not None:
        seconds = float(args.expected_seconds)
        return seconds, {
            "strategy": "explicit_seconds",
            "seconds": seconds,
            "game_timer": _format_seconds(seconds),
        }
    if args.expected_timer:
        seconds = _parse_timer_label(args.expected_timer)
        return seconds, {
            "strategy": "explicit_timer",
            "raw": args.expected_timer,
            "seconds": seconds,
            "game_timer": _format_seconds(seconds) if seconds is not None else None,
        }
    if args.ground_truth_address is not None:
        direct = read_timeline_playtime_address(reader, args.ground_truth_address)
        if direct.get("status") == "OK" and direct.get("seconds") is not None:
            seconds = float(direct["seconds"])
            return seconds, {
                "strategy": "pause_menu_timeline_playtime_address",
                "address": direct.get("address"),
                "raw": direct.get("raw"),
                "seconds": seconds,
                "game_timer": direct.get("game_timer"),
                "note": "pause-menu render/cache truth, used only to seed numeric candidate search",
            }
        return None, {
            "strategy": "pause_menu_timeline_playtime_address",
            "address": f"0x{args.ground_truth_address:016x}",
            "status": direct.get("status"),
            "reason": direct.get("reason") or "ground truth address did not return a timer",
        }
    context = scan_context_timers(
        reader,
        max_region_size=args.max_region_size,
        max_hits=args.max_context_hits,
    )
    selected = select_visible_timer_context(
        context,
        max_visible_seconds=args.max_visible_timer_seconds,
    )
    if selected and selected.get("seconds") is not None:
        seconds = float(selected["seconds"])
        return seconds, {
            "strategy": "visible_context_seed",
            "seconds": seconds,
            "game_timer": selected.get("game_timer"),
            "selected_timer": selected,
            "note": "diagnostic seed only; visible context may be a stale rendered string",
        }
    return None, {
        "strategy": "none",
        "reason": "no explicit timer, ground-truth address, or visible context seed found",
    }


def cmd_scan_numeric(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        expected, selection = _resolve_numeric_expected_seconds(args, reader)
        if expected is None:
            payload = {
                "status": "NO_EXPECTED_TIMER",
                "pid": pid,
                "module": module.__dict__ if module else None,
                "expected_selection": selection,
            }
            print(json.dumps(payload, indent=2))
            return 1
        kinds = _parse_numeric_kinds(args.kinds)
        numeric_scan = scan_numeric_timer_candidates(
            reader,
            expected_seconds=expected,
            seconds_window=args.seconds_window,
            max_timer_seconds=args.max_timer_seconds,
            max_region_size=args.max_region_size,
            max_candidates_per_kind=args.max_candidates_per_kind,
            kinds=kinds,
            include_readonly=args.include_readonly,
        )

    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "expected_selection": selection,
        "numeric_scan": numeric_scan,
        "notes": [
            "This scan is intended to run while paused; it uses pause-menu Playtime only as a seed.",
            "Candidates are not trusted until a live track plus re-pause score validates movement and final value.",
            "The pause-menu Timeline Playtime string address is a rendered/cache oracle, not the live timer.",
        ],
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    console_payload = (
        payload
        if args.full_output
        else summarize_numeric_scan_for_console(payload, output_path)
    )
    print(json.dumps(console_payload, indent=2))
    return 0


def _load_numeric_scan_candidates(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scan = payload.get("numeric_scan") or payload
    candidates = [
        candidate for candidate in (scan.get("candidates") or [])
        if isinstance(candidate, dict)
    ]
    return payload, candidates


def cmd_track_numeric(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    scan_payload, candidates = _load_numeric_scan_candidates(Path(args.candidates))
    candidates.sort(
        key=lambda item: (
            float(item.get("distance_seconds", 999999.0)),
            str(item.get("kind")),
            int(str(item.get("address")), 16),
        )
    )
    candidates = candidates[:args.candidate_limit]
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        tracks = _candidate_tracks(
            reader,
            candidates,
            samples=args.samples,
            interval_seconds=args.interval_seconds,
        )

    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "source_scan": {
            "path": str(Path(args.candidates)),
            "expected_selection": scan_payload.get("expected_selection"),
            "expected_seconds": (scan_payload.get("numeric_scan") or {}).get("expected_seconds"),
            "candidate_count": len((scan_payload.get("numeric_scan") or {}).get("candidates") or []),
        },
        "tracked_candidate_count": len(candidates),
        "interval_seconds": args.interval_seconds,
        **tracks,
        "notes": [
            "Run this only during the controlled unpaused window.",
            "Use score-numeric after re-pausing to reject moving counters that do not land on pause-menu Playtime.",
        ],
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    summary = {
        "status": payload["status"],
        "pid": pid,
        "tracked_candidate_count": payload["tracked_candidate_count"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "track_count": payload["track_count"],
        "moving_like_timer_count": sum(
            1 for track in payload["tracks"] if track.get("moving_like_timer")
        ),
        "top_tracks": payload["tracks"][:20],
    }
    if output_path:
        summary["output"] = output_path
    print(json.dumps(payload if args.full_output else summary, indent=2))
    return 0


def cmd_track_address(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    candidate = {
        "address": f"0x{args.address:016x}",
        "kind": args.kind,
        "width": NUMERIC_TIMER_KIND_BY_NAME.get(args.kind).width
        if args.kind in NUMERIC_TIMER_KIND_BY_NAME
        else None,
    }
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        tracks = _candidate_tracks(
            reader,
            [candidate],
            samples=args.samples,
            interval_seconds=args.interval_seconds,
        )
    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "tracked_candidate_count": 1,
        "interval_seconds": args.interval_seconds,
        **tracks,
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    summary = {
        "status": payload["status"],
        "pid": pid,
        "elapsed_seconds": payload["elapsed_seconds"],
        "moving_like_timer_count": sum(
            1 for track in payload["tracks"] if track.get("moving_like_timer")
        ),
        "tracks": payload["tracks"],
    }
    if output_path:
        summary["output"] = output_path
    print(json.dumps(payload if args.full_output else summary, indent=2))
    return 0


def cmd_hunt_numeric(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        expected, selection = _resolve_numeric_expected_seconds(args, reader)
        if expected is None:
            payload = {
                "status": "NO_EXPECTED_TIMER",
                "pid": pid,
                "module": module.__dict__ if module else None,
                "expected_selection": selection,
            }
            print(json.dumps(payload, indent=2))
            return 1
        kinds = _parse_numeric_kinds(args.kinds)
        scan_started = time.time()
        numeric_scan = scan_numeric_timer_candidates(
            reader,
            expected_seconds=expected,
            seconds_window=args.seconds_window,
            max_timer_seconds=args.max_timer_seconds,
            max_region_size=args.max_region_size,
            max_candidates_per_kind=args.max_candidates_per_kind,
            kinds=kinds,
            include_readonly=args.include_readonly,
        )
        candidates = [
            candidate for candidate in numeric_scan.get("candidates", [])
            if isinstance(candidate, dict)
        ]
        candidates = candidates[:args.candidate_limit]
        tracks = _candidate_tracks(
            reader,
            candidates,
            samples=args.samples,
            interval_seconds=args.interval_seconds,
        )

    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "expected_selection": selection,
        "scan_started_at": scan_started,
        "tracked_candidate_count": len(candidates),
        "interval_seconds": args.interval_seconds,
        "numeric_scan": numeric_scan,
        **tracks,
        "notes": [
            "Run this only during a controlled unpaused window.",
            "The scan seed may be approximate during live hunts; score-numeric can ignore start truth and rely on final re-pause truth.",
        ],
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    summary = {
        "status": payload["status"],
        "pid": pid,
        "expected_timer": numeric_scan["expected_timer"],
        "search_range": numeric_scan["search_range"],
        "candidate_count": numeric_scan["candidate_count"],
        "candidate_count_by_kind": numeric_scan["candidate_count_by_kind"],
        "tracked_candidate_count": payload["tracked_candidate_count"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "moving_like_timer_count": sum(
            1 for track in payload["tracks"] if track.get("moving_like_timer")
        ),
        "top_tracks": payload["tracks"][:20],
    }
    if output_path:
        summary["output"] = output_path
    print(json.dumps(payload if args.full_output else summary, indent=2))
    return 0


def cmd_score_numeric(args: argparse.Namespace) -> int:
    pid = args.pid or _find_breach_pid()
    if pid is None:
        print("Could not find Breach.exe; pass --pid", flush=True)
        return 2
    scan_payload, _candidates = _load_numeric_scan_candidates(Path(args.scan))
    track_payload = json.loads(Path(args.track).read_text(encoding="utf-8"))
    start_truth = None if args.ignore_start_truth else (scan_payload.get("numeric_scan") or {}).get("expected_seconds")
    try:
        start_truth_seconds = float(start_truth)
    except (TypeError, ValueError):
        start_truth_seconds = None

    with WindowsProcessReader(pid) as reader:
        module = reader.module()
        final_truth: dict[str, Any] | None = None
        final_truth_seconds: float | None = None
        if args.final_expected_seconds is not None:
            final_truth_seconds = float(args.final_expected_seconds)
            final_truth = {
                "strategy": "explicit_seconds",
                "seconds": final_truth_seconds,
                "game_timer": _format_seconds(final_truth_seconds),
            }
        elif args.final_expected_timer:
            final_truth_seconds = _parse_timer_label(args.final_expected_timer)
            final_truth = {
                "strategy": "explicit_timer",
                "raw": args.final_expected_timer,
                "seconds": final_truth_seconds,
                "game_timer": (
                    _format_seconds(final_truth_seconds)
                    if final_truth_seconds is not None
                    else None
                ),
            }
        elif args.ground_truth_address is not None:
            direct = read_timeline_playtime_address(reader, args.ground_truth_address)
            final_truth = {
                "strategy": "pause_menu_timeline_playtime_address",
                "address": f"0x{args.ground_truth_address:016x}",
                "result": direct,
                "note": "pause-menu render/cache truth after re-pausing",
            }
            if direct.get("status") == "OK" and direct.get("seconds") is not None:
                final_truth_seconds = float(direct["seconds"])

        tracks = [
            track for track in (track_payload.get("tracks") or [])
            if isinstance(track, dict) and isinstance(track.get("candidate"), dict)
        ]
        candidates = [track["candidate"] for track in tracks]
        current_values = {
            _numeric_candidate_key(candidate): _read_numeric_candidate(reader, candidate)
            for candidate in candidates
        }
        if args.pause_stability_seconds > 0:
            time.sleep(args.pause_stability_seconds)
        stable_values = {
            _numeric_candidate_key(candidate): _read_numeric_candidate(reader, candidate)
            for candidate in candidates
        }
        scored = _score_numeric_tracks(
            tracks=tracks,
            start_truth_seconds=start_truth_seconds,
            final_truth_seconds=final_truth_seconds,
            current_values=current_values,
            stable_values=stable_values,
            max_results=args.max_results,
        )

    payload = {
        "status": "OK",
        "pid": pid,
        "created_at": time.time(),
        "module": module.__dict__ if module else None,
        "source_scan": str(Path(args.scan)),
        "source_track": str(Path(args.track)),
        "start_truth_seconds": start_truth_seconds,
        "start_truth_timer": (
            _format_seconds(start_truth_seconds)
            if start_truth_seconds is not None
            else None
        ),
        "final_truth": final_truth,
        "final_truth_seconds": final_truth_seconds,
        "final_truth_timer": (
            _format_seconds(final_truth_seconds)
            if final_truth_seconds is not None
            else None
        ),
        "pause_stability_seconds": args.pause_stability_seconds,
        "scored_count": len(scored),
        "validated_count": sum(
            1 for item in scored
            if item.get("status") == "validated_cycle_candidate"
        ),
        "results": scored,
        "notes": [
            "validated_cycle_candidate means start value, live movement, re-paused final value, and paused stability all agree.",
            "A validated candidate is still process-local and should survive another cycle before becoming the screenshot frame clock.",
        ],
    }
    output_path: str | None = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        output_path = str(path)
    summary = {
        "status": payload["status"],
        "pid": pid,
        "start_truth_timer": payload["start_truth_timer"],
        "final_truth_timer": payload["final_truth_timer"],
        "validated_count": payload["validated_count"],
        "top_results": payload["results"][:20],
    }
    if output_path:
        summary["output"] = output_path
    print(json.dumps(payload if args.full_output else summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Scan and validate timer candidates")
    scan.add_argument("--pid", type=int)
    scan.add_argument("--expected-seconds", type=float)
    scan.add_argument("--expected-timer")
    scan.add_argument("--expected-selection", choices=("mode", "max"), default="mode")
    scan.add_argument("--sample-seconds", type=float, default=2.5)
    scan.add_argument("--max-region-size", type=int, default=32 * 1024 * 1024)
    scan.add_argument("--max-context-hits", type=int, default=200)
    scan.add_argument("--max-visible-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    scan.add_argument("--max-candidates", type=int, default=20000)
    scan.add_argument("--max-results", type=int, default=25)
    scan.add_argument("--max-field-offset", type=int, default=0x20000)
    scan.add_argument("--max-pointer-roots", type=int, default=25)
    scan.add_argument("--full-output", action="store_true")
    scan.add_argument("--output")
    scan.set_defaults(func=cmd_scan)

    watch = sub.add_parser(
        "watch-context",
        help="Infer pause state by checking whether visible timer strings advance",
    )
    watch.add_argument("--pid", type=int)
    watch.add_argument("--sample-seconds", type=float, default=5.0)
    watch.add_argument("--samples", type=int, default=2)
    watch.add_argument("--movement-threshold", type=float, default=1.0)
    watch.add_argument("--max-region-size", type=int, default=32 * 1024 * 1024)
    watch.add_argument("--max-context-hits", type=int, default=240)
    watch.add_argument("--max-visible-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    watch.add_argument("--max-summary", type=int, default=12)
    watch.add_argument("--output")
    watch.set_defaults(func=cmd_watch_context)

    read_address = sub.add_parser(
        "read-address",
        help="Read a calibrated pause-menu Timeline Playtime string address",
    )
    read_address.add_argument("address", type=_parse_int_auto)
    read_address.add_argument("--pid", type=int)
    read_address.add_argument("--bytes", type=int, default=64)
    read_address.set_defaults(func=cmd_read_address)

    read_numeric = sub.add_parser(
        "read-numeric",
        help="Read one numeric timer candidate address",
    )
    read_numeric.add_argument("address", type=_parse_int_auto)
    read_numeric.add_argument("kind", choices=sorted(NUMERIC_TIMER_KIND_BY_NAME))
    read_numeric.add_argument("--pid", type=int)
    read_numeric.set_defaults(func=cmd_read_numeric)

    scan_numeric = sub.add_parser(
        "scan-numeric",
        help="Scan paused memory for numeric timer candidates near a ground-truth timer",
    )
    scan_numeric.add_argument("--pid", type=int)
    scan_numeric.add_argument("--expected-seconds", type=float)
    scan_numeric.add_argument("--expected-timer")
    scan_numeric.add_argument("--ground-truth-address", type=_parse_int_auto)
    scan_numeric.add_argument("--seconds-window", type=float, default=8.0)
    scan_numeric.add_argument("--max-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    scan_numeric.add_argument("--max-region-size", type=int, default=32 * 1024 * 1024)
    scan_numeric.add_argument("--max-context-hits", type=int, default=240)
    scan_numeric.add_argument("--max-visible-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    scan_numeric.add_argument("--max-candidates-per-kind", type=int, default=2000)
    scan_numeric.add_argument("--kinds", default="all")
    scan_numeric.add_argument("--include-readonly", action="store_true")
    scan_numeric.add_argument("--full-output", action="store_true")
    scan_numeric.add_argument("--output")
    scan_numeric.set_defaults(func=cmd_scan_numeric)

    track_numeric = sub.add_parser(
        "track-numeric",
        help="Track numeric candidates during a controlled unpaused window",
    )
    track_numeric.add_argument("candidates")
    track_numeric.add_argument("--pid", type=int)
    track_numeric.add_argument("--samples", type=int, default=11)
    track_numeric.add_argument("--interval-seconds", type=float, default=0.5)
    track_numeric.add_argument("--candidate-limit", type=int, default=5000)
    track_numeric.add_argument("--full-output", action="store_true")
    track_numeric.add_argument("--output")
    track_numeric.set_defaults(func=cmd_track_numeric)

    track_address = sub.add_parser(
        "track-address",
        help="Track one numeric timer candidate address",
    )
    track_address.add_argument("address", type=_parse_int_auto)
    track_address.add_argument("kind", choices=sorted(NUMERIC_TIMER_KIND_BY_NAME))
    track_address.add_argument("--pid", type=int)
    track_address.add_argument("--samples", type=int, default=9)
    track_address.add_argument("--interval-seconds", type=float, default=0.5)
    track_address.add_argument("--full-output", action="store_true")
    track_address.add_argument("--output")
    track_address.set_defaults(func=cmd_track_address)

    hunt_numeric = sub.add_parser(
        "hunt-numeric",
        help="Scan and immediately track numeric candidates during a live window",
    )
    hunt_numeric.add_argument("--pid", type=int)
    hunt_numeric.add_argument("--expected-seconds", type=float)
    hunt_numeric.add_argument("--expected-timer")
    hunt_numeric.add_argument("--ground-truth-address", type=_parse_int_auto)
    hunt_numeric.add_argument("--seconds-window", type=float, default=20.0)
    hunt_numeric.add_argument("--max-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    hunt_numeric.add_argument("--max-region-size", type=int, default=8 * 1024 * 1024)
    hunt_numeric.add_argument("--max-context-hits", type=int, default=240)
    hunt_numeric.add_argument("--max-visible-timer-seconds", type=float, default=DEFAULT_MAX_VISIBLE_TIMER_SECONDS)
    hunt_numeric.add_argument("--max-candidates-per-kind", type=int, default=500)
    hunt_numeric.add_argument("--kinds", default="all")
    hunt_numeric.add_argument("--include-readonly", action="store_true")
    hunt_numeric.add_argument("--samples", type=int, default=11)
    hunt_numeric.add_argument("--interval-seconds", type=float, default=0.5)
    hunt_numeric.add_argument("--candidate-limit", type=int, default=1000)
    hunt_numeric.add_argument("--full-output", action="store_true")
    hunt_numeric.add_argument("--output")
    hunt_numeric.set_defaults(func=cmd_hunt_numeric)

    score_numeric = sub.add_parser(
        "score-numeric",
        help="Score a live numeric track after re-pausing against Timeline Playtime",
    )
    score_numeric.add_argument("scan")
    score_numeric.add_argument("track")
    score_numeric.add_argument("--pid", type=int)
    score_numeric.add_argument("--ground-truth-address", type=_parse_int_auto)
    score_numeric.add_argument("--final-expected-seconds", type=float)
    score_numeric.add_argument("--final-expected-timer")
    score_numeric.add_argument("--ignore-start-truth", action="store_true")
    score_numeric.add_argument("--pause-stability-seconds", type=float, default=1.0)
    score_numeric.add_argument("--max-results", type=int, default=40)
    score_numeric.add_argument("--full-output", action="store_true")
    score_numeric.add_argument("--output")
    score_numeric.set_defaults(func=cmd_score_numeric)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
