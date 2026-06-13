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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
