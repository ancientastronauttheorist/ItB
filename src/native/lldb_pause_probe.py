"""LLDB-assisted pause-menu memory probe for Into the Breach.

The normal bridge command poller runs from Mission.BaseUpdate, so it can go
quiet on non-mission screens or when the pause menu freezes mission updates.
This diagnostic attaches with LLDB, samples writable memory, detaches, toggles
Esc, samples again, and reports addresses whose bytes follow:

    closed sample == closed2 sample != open sample

Usage:
    python3 src/native/lldb_pause_probe.py run

The same file is imported by LLDB; do not call the LLDB command by hand unless
you are debugging the sampler:

    lldb -p <pid> -o "command script import src/native/lldb_pause_probe.py" \
        -o "itb_pause_dump /tmp/itb_pause_probe/sample_closed closed"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

try:
    import lldb  # type: ignore
except Exception:  # Normal Python driver mode.
    lldb = None  # type: ignore


DEFAULT_MAX_REGION = 64 * 1024 * 1024
DEFAULT_MAX_TOTAL = 512 * 1024 * 1024
DEFAULT_MAX_CANDIDATES = 200
DEFAULT_PAUSE_IMAGE_OFFSET: int | None = None
DEFAULT_PAUSE_OPEN_VALUE = 1
SKIP_VMMAP_LABELS = {"IOSurface"}


def _find_game_pid() -> int | None:
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "Into the Breach"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    pids: list[int] = []
    for raw in proc.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            pids.append(int(raw))
        except ValueError:
            continue
    return pids[0] if pids else None


def _read_process_memory(process: Any, addr: int, size: int) -> bytes | None:
    if lldb is None:
        return None
    error = lldb.SBError()
    data = process.ReadMemory(addr, size, error)
    if error.Success():
        return bytes(data)
    return None


def _region_prot(region: Any) -> str:
    bits = []
    bits.append("r" if region.IsReadable() else "-")
    bits.append("w" if region.IsWritable() else "-")
    bits.append("x" if region.IsExecutable() else "-")
    return "".join(bits)


def _vmmap_regions(pid: int) -> dict[tuple[int, int], dict[str, str]]:
    try:
        proc = subprocess.run(
            ["vmmap", str(pid)],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}

    regions: dict[tuple[int, int], dict[str, str]] = {}
    for line in proc.stdout.splitlines():
        match = re.search(r"([0-9A-Fa-f]{8,16})-([0-9A-Fa-f]{8,16})", line)
        if not match:
            continue
        label = line.split()[0] if line.split() else ""
        start = int(match.group(1), 16)
        end = int(match.group(2), 16)
        regions[(start, end)] = {"label": label, "line": line.strip()}
    return regions


def _lldb_dump_sample(debugger: Any, command: str, result: Any, internal_dict: dict) -> None:
    """LLDB command: dump readable+writable memory regions to a sample dir."""
    if lldb is None:
        print("lldb module is unavailable")
        return

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        print(f"argument parse failed: {exc}")
        return
    if len(tokens) < 2:
        print(
            "usage: itb_pause_dump SAMPLE_DIR LABEL "
            "[--max-region BYTES] [--max-total BYTES]"
        )
        return

    sample_dir = Path(tokens[0])
    label = tokens[1]
    max_region = DEFAULT_MAX_REGION
    max_total = DEFAULT_MAX_TOTAL
    i = 2
    while i < len(tokens):
        if tokens[i] == "--max-region" and i + 1 < len(tokens):
            max_region = int(tokens[i + 1])
            i += 2
        elif tokens[i] == "--max-total" and i + 1 < len(tokens):
            max_total = int(tokens[i + 1])
            i += 2
        else:
            print(f"unknown argument: {tokens[i]}")
            return

    sample_dir.mkdir(parents=True, exist_ok=True)
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    if not process or not process.IsValid():
        print("No valid LLDB process. Attach to the game first.")
        return

    vmmap = _vmmap_regions(int(process.GetProcessID()))
    region_list = process.GetMemoryRegions()
    manifest: dict[str, Any] = {
        "label": label,
        "created_at": time.time(),
        "max_region": max_region,
        "max_total": max_total,
        "regions": [],
        "skipped": [],
    }

    total = 0
    dumped = 0
    for idx in range(region_list.GetSize()):
        region = lldb.SBMemoryRegionInfo()
        region_list.GetMemoryRegionAtIndex(idx, region)
        start = int(region.GetRegionBase())
        end = int(region.GetRegionEnd())
        size = max(0, end - start)
        prot = _region_prot(region)
        vmmap_entry = vmmap.get((start, end), {})
        vmmap_label = vmmap_entry.get("label", "")

        if not region.IsReadable() or not region.IsWritable():
            continue
        if vmmap_label in SKIP_VMMAP_LABELS:
            manifest["skipped"].append({
                "base": start,
                "size": size,
                "reason": "vmmap_label",
                "vmmap_label": vmmap_label,
                "prot": prot,
            })
            continue
        if region.IsExecutable():
            manifest["skipped"].append({
                "base": start,
                "size": size,
                "reason": "executable",
                "prot": prot,
            })
            continue
        if size <= 0 or size > max_region:
            manifest["skipped"].append({
                "base": start,
                "size": size,
                "reason": "size",
                "prot": prot,
            })
            continue
        if total + size > max_total:
            manifest["skipped"].append({
                "base": start,
                "size": size,
                "reason": "total_cap",
                "prot": prot,
            })
            continue

        data = _read_process_memory(process, start, size)
        if data is None or len(data) != size:
            manifest["skipped"].append({
                "base": start,
                "size": size,
                "reason": "read_failed",
                "prot": prot,
            })
            continue

        filename = f"region_{dumped:04d}_{start:016x}_{size:x}.bin"
        (sample_dir / filename).write_bytes(data)
        manifest["regions"].append({
            "base": start,
            "end": end,
            "size": size,
            "prot": prot,
            "vmmap_label": vmmap_label,
            "file": filename,
        })
        total += size
        dumped += 1

    manifest["dumped_regions"] = dumped
    manifest["dumped_bytes"] = total
    (sample_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        f"pause sample {label}: dumped {dumped} regions, "
        f"{total / 1024 / 1024:.1f} MB to {sample_dir}"
    )
    process.Detach()


def _lldb_read_values(debugger: Any, command: str, result: Any, internal_dict: dict) -> None:
    """LLDB command: read a candidate list into a small JSON value sample."""
    if lldb is None:
        print("lldb module is unavailable")
        return

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        print(f"argument parse failed: {exc}")
        return
    if len(tokens) < 3:
        print("usage: itb_pause_read CANDIDATES_JSON OUT_JSON LABEL [LIMIT]")
        return

    candidates_path = Path(tokens[0])
    output_path = Path(tokens[1])
    label = tokens[2]
    limit = int(tokens[3]) if len(tokens) >= 4 else DEFAULT_MAX_CANDIDATES

    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    if not process or not process.IsValid():
        print("No valid LLDB process. Attach to the game first.")
        return

    payload = json.loads(candidates_path.read_text())
    candidates = payload.get("candidates") or []
    values: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        if not isinstance(candidate, dict):
            continue
        addr = int(str(candidate.get("address")), 16)
        width = int(candidate.get("width") or 1)
        data = _read_process_memory(process, addr, width)
        entry = {
            "address": f"0x{addr:016x}",
            "width": width,
            "read_ok": data is not None and len(data) == width,
            "source_candidate": candidate,
        }
        if data is not None and len(data) == width:
            entry["bytes"] = data.hex()
            entry["value"] = int.from_bytes(data, "little", signed=False)
        values.append(entry)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "label": label,
        "created_at": time.time(),
        "values": values,
    }, indent=2))
    print(f"read {len(values)} candidate values to {output_path}")
    process.Detach()


def _find_game_module(target: Any) -> Any | None:
    if lldb is None:
        return None
    for idx in range(target.GetNumModules()):
        module = target.GetModuleAtIndex(idx)
        file_spec = module.GetFileSpec()
        filename = file_spec.GetFilename() if file_spec else ""
        if filename == "Into the Breach":
            return module
    return None


def _module_section_base(module: Any, target: Any, section_name: str) -> int | None:
    section = module.FindSection(section_name)
    if not section or not section.IsValid():
        return None
    addr = int(section.GetLoadAddress(target))
    if addr == int(lldb.LLDB_INVALID_ADDRESS):
        return None
    return addr


def _lldb_read_pause_offset(debugger: Any, command: str, result: Any, internal_dict: dict) -> None:
    """LLDB command: read the pause byte by main-image-relative offset."""
    if lldb is None:
        print("lldb module is unavailable")
        return

    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        print(f"argument parse failed: {exc}")
        return
    if len(tokens) < 2:
        print(
            "usage: itb_pause_read_offset OUT_JSON LABEL "
            "[--image-offset HEX] [--width BYTES] [--open-value INT]"
        )
        return

    output_path = Path(tokens[0])
    label = tokens[1]
    image_offset = DEFAULT_PAUSE_IMAGE_OFFSET
    width = 1
    open_value = DEFAULT_PAUSE_OPEN_VALUE
    i = 2
    while i < len(tokens):
        if tokens[i] == "--image-offset" and i + 1 < len(tokens):
            image_offset = int(tokens[i + 1], 0)
            i += 2
        elif tokens[i] == "--width" and i + 1 < len(tokens):
            width = int(tokens[i + 1], 0)
            i += 2
        elif tokens[i] == "--open-value" and i + 1 < len(tokens):
            open_value = int(tokens[i + 1], 0)
            i += 2
        else:
            print(f"unknown argument: {tokens[i]}")
            return
    if image_offset is None:
        print("No verified default pause offset yet; pass --image-offset.")
        return

    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    if not process or not process.IsValid():
        print("No valid LLDB process. Attach to the game first.")
        return

    module = _find_game_module(target)
    if module is None:
        print("Could not find Into the Breach main module.")
        process.Detach()
        return

    text_base = _module_section_base(module, target, "__TEXT")
    if text_base is None:
        print("Could not resolve __TEXT load address for the main module.")
        process.Detach()
        return

    address = text_base + image_offset
    data = _read_process_memory(process, address, width)
    entry: dict[str, Any] = {
        "label": label,
        "created_at": time.time(),
        "image_base": f"0x{text_base:016x}",
        "image_offset": f"0x{image_offset:x}",
        "address": f"0x{address:016x}",
        "width": width,
        "open_value": open_value,
        "read_ok": data is not None and len(data) == width,
    }
    if data is not None and len(data) == width:
        value = int.from_bytes(data, "little", signed=False)
        entry["bytes"] = data.hex()
        entry["value"] = value
        entry["pause_menu_open"] = value == open_value

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(entry, indent=2))
    print(f"read pause offset to {output_path}")
    process.Detach()


def __lldb_init_module(debugger: Any, internal_dict: dict) -> None:
    debugger.HandleCommand(
        "command script add -f lldb_pause_probe._lldb_dump_sample itb_pause_dump"
    )
    debugger.HandleCommand(
        "command script add -f lldb_pause_probe._lldb_read_values itb_pause_read"
    )
    debugger.HandleCommand(
        "command script add -f lldb_pause_probe._lldb_read_pause_offset "
        "itb_pause_read_offset"
    )
    print("ITB pause memory probe loaded. Commands: itb_pause_dump, itb_pause_read_offset")


def _run_lldb_sample(
    *,
    pid: int,
    sample_dir: Path,
    label: str,
    max_region: int,
    max_total: int,
    lldb_path: str,
) -> None:
    script_path = Path(__file__).resolve()
    cmd = [
        lldb_path,
        "--batch",
        "-p",
        str(pid),
        "-o",
        f"command script import {script_path}",
        "-o",
        (
            f"itb_pause_dump {shlex.quote(str(sample_dir))} {shlex.quote(label)} "
            f"--max-region {max_region} --max-total {max_total}"
        ),
        "-o",
        "quit",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "Not allowed to attach to process" in detail:
            raise RuntimeError(
                "LLDB attach was denied by macOS. Developer mode is probably "
                "disabled for debugging other processes. Run "
                "`DevToolsSecurity -status` to confirm, then enable it from an "
                "administrator shell with `sudo DevToolsSecurity -enable`."
            )
        raise RuntimeError(
            "LLDB sample failed\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    if not (sample_dir / "manifest.json").exists():
        raise RuntimeError(
            "LLDB sample produced no manifest\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _run_lldb_read_values(
    *,
    pid: int,
    candidates_path: Path,
    output_path: Path,
    label: str,
    limit: int,
    lldb_path: str,
) -> None:
    script_path = Path(__file__).resolve()
    cmd = [
        lldb_path,
        "--batch",
        "-p",
        str(pid),
        "-o",
        f"command script import {script_path}",
        "-o",
        (
            f"itb_pause_read {shlex.quote(str(candidates_path))} "
            f"{shlex.quote(str(output_path))} {shlex.quote(label)} {limit}"
        ),
        "-o",
        "quit",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "Not allowed to attach to process" in detail:
            raise RuntimeError(
                "LLDB attach was denied by macOS. Re-check the app signature "
                "and get-task-allow entitlement."
            )
        raise RuntimeError(
            "LLDB value read failed\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    if not output_path.exists():
        raise RuntimeError(
            "LLDB value read produced no output\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _run_lldb_read_pause_offset(
    *,
    pid: int,
    output_path: Path,
    label: str,
    image_offset: int,
    width: int,
    open_value: int,
    lldb_path: str,
) -> None:
    script_path = Path(__file__).resolve()
    cmd = [
        lldb_path,
        "--batch",
        "-p",
        str(pid),
        "-o",
        f"command script import {script_path}",
        "-o",
        (
            f"itb_pause_read_offset {shlex.quote(str(output_path))} "
            f"{shlex.quote(label)} --image-offset 0x{image_offset:x} "
            f"--width {width} --open-value {open_value}"
        ),
        "-o",
        "quit",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "Not allowed to attach to process" in detail:
            raise RuntimeError(
                "LLDB attach was denied by macOS. Re-check the app signature "
                "and get-task-allow entitlement."
            )
        raise RuntimeError(
            "LLDB pause offset read failed\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    if not output_path.exists():
        raise RuntimeError(
            "LLDB pause offset read produced no output\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _toggle_esc(settle_seconds: float) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.control.mac_click import press_key

    return press_key(
        "esc",
        description="Toggle pause menu for LLDB pause probe",
        settle_seconds=settle_seconds,
    )


def _load_manifest(sample_dir: Path) -> dict[str, Any]:
    return json.loads((sample_dir / "manifest.json").read_text())


def _region_map(sample_dir: Path) -> dict[tuple[int, int], dict[str, Any]]:
    manifest = _load_manifest(sample_dir)
    out: dict[tuple[int, int], dict[str, Any]] = {}
    for region in manifest.get("regions") or []:
        if not isinstance(region, dict):
            continue
        key = (int(region["base"]), int(region["size"]))
        out[key] = region
    return out


def _candidate_score(closed: int, open_value: int, *, width: int, addr: int) -> int:
    score = 0
    if width == 1:
        if (closed, open_value) in ((0, 1), (1, 0), (0, 255), (255, 0)):
            score += 100
        if closed in (0, 1, 255) and open_value in (0, 1, 255):
            score += 40
    else:
        if (closed, open_value) in ((0, 1), (1, 0)):
            score += 120
        if 0 <= closed <= 16 and 0 <= open_value <= 16:
            score += 50
    if addr % width == 0:
        score += 5
    return score


def _compare_samples(
    root: Path,
    *,
    max_candidates: int,
) -> dict[str, Any]:
    closed_dir = root / "sample_closed"
    open_dir = root / "sample_open"
    closed2_dir = root / "sample_closed2"
    c1 = _region_map(closed_dir)
    op = _region_map(open_dir)
    c2 = _region_map(closed2_dir)
    common_keys = sorted(set(c1) & set(op) & set(c2))

    candidates: list[dict[str, Any]] = []
    byte_pair_counts: dict[str, int] = {}
    regions_compared = 0
    bytes_compared = 0
    toggled_byte_count = 0

    for key in common_keys:
        base, size = key
        r1 = c1[key]
        ro = op[key]
        r2 = c2[key]
        b1 = (closed_dir / r1["file"]).read_bytes()
        bo = (open_dir / ro["file"]).read_bytes()
        b2 = (closed2_dir / r2["file"]).read_bytes()
        n = min(len(b1), len(bo), len(b2))
        if n == 0:
            continue
        regions_compared += 1
        bytes_compared += n

        # Byte candidates.
        for offset in range(n):
            closed = b1[offset]
            open_value = bo[offset]
            if closed == b2[offset] and closed != open_value:
                toggled_byte_count += 1
                pair_key = f"{closed}->{open_value}"
                byte_pair_counts[pair_key] = byte_pair_counts.get(pair_key, 0) + 1
                score = _candidate_score(closed, open_value, width=1, addr=base + offset)
                if score > 0:
                    candidates.append({
                        "address": f"0x{base + offset:016x}",
                        "region_base": f"0x{base:016x}",
                        "offset": offset,
                        "width": 1,
                        "closed": closed,
                        "open": open_value,
                        "closed2": b2[offset],
                        "score": score,
                    })

        # Aligned int32 candidates. This catches classic enum/bool storage.
        limit = n - (n % 4)
        for offset in range(0, limit, 4):
            v1 = int.from_bytes(b1[offset:offset + 4], "little", signed=False)
            vo = int.from_bytes(bo[offset:offset + 4], "little", signed=False)
            v2 = int.from_bytes(b2[offset:offset + 4], "little", signed=False)
            if v1 == v2 and v1 != vo and v1 <= 16 and vo <= 16:
                candidates.append({
                    "address": f"0x{base + offset:016x}",
                    "region_base": f"0x{base:016x}",
                    "offset": offset,
                    "width": 4,
                    "closed": v1,
                    "open": vo,
                    "closed2": v2,
                    "score": _candidate_score(v1, vo, width=4, addr=base + offset),
                })

    candidates.sort(
        key=lambda item: (
            -int(item["score"]),
            int(item["address"], 16),
            int(item["width"]),
        )
    )
    candidates = candidates[:max_candidates]
    result = {
        "status": "OK",
        "root": str(root),
        "regions_compared": regions_compared,
        "bytes_compared": bytes_compared,
        "toggled_byte_count": toggled_byte_count,
        "byte_pair_counts_top": sorted(
            byte_pair_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20],
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    (root / "pause_probe_candidates.json").write_text(json.dumps(result, indent=2))
    return result


def cmd_run(args: argparse.Namespace) -> int:
    pid = args.pid or _find_game_pid()
    if not pid:
        print("Into the Breach process not found.", file=sys.stderr)
        return 2

    lldb_path = args.lldb or shutil.which("lldb")
    if not lldb_path:
        print("lldb not found on PATH.", file=sys.stderr)
        return 2

    if args.output:
        root = Path(args.output).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="itb_pause_probe_"))

    print(f"PID: {pid}")
    print(f"Output: {root}")
    print("Sample 1: current state, expected pause closed.")
    try:
        _run_lldb_sample(
            pid=pid,
            sample_dir=root / "sample_closed",
            label="closed",
            max_region=args.max_region,
            max_total=args.max_total,
            lldb_path=lldb_path,
        )

        if not args.no_toggle:
            print("Toggling Esc to expected pause open.")
            toggle = _toggle_esc(args.settle_seconds)
            print(f"Esc toggle 1: {toggle.get('status')} {toggle.get('error', '')}")
            if toggle.get("status") != "OK":
                return 3
        else:
            print("Skipping Esc toggle 1 by request.")

        print("Sample 2: expected pause open.")
        _run_lldb_sample(
            pid=pid,
            sample_dir=root / "sample_open",
            label="open",
            max_region=args.max_region,
            max_total=args.max_total,
            lldb_path=lldb_path,
        )

        if not args.no_toggle:
            print("Toggling Esc to expected pause closed again.")
            toggle = _toggle_esc(args.settle_seconds)
            print(f"Esc toggle 2: {toggle.get('status')} {toggle.get('error', '')}")
            if toggle.get("status") != "OK":
                return 3
        else:
            print("Skipping Esc toggle 2 by request.")

        print("Sample 3: expected pause closed again.")
        _run_lldb_sample(
            pid=pid,
            sample_dir=root / "sample_closed2",
            label="closed2",
            max_region=args.max_region,
            max_total=args.max_total,
            lldb_path=lldb_path,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Partial output, if any: {root}", file=sys.stderr)
        return 4

    result = _compare_samples(root, max_candidates=args.max_candidates)
    print("\n=== PAUSE PROBE RESULT ===")
    print(f"regions compared: {result['regions_compared']}")
    print(f"bytes compared:   {result['bytes_compared'] / 1024 / 1024:.1f} MB")
    print(f"toggled bytes:    {result['toggled_byte_count']}")
    print(f"candidates:       {result['candidate_count']}")
    print(f"saved:            {root / 'pause_probe_candidates.json'}")
    for candidate in result["candidates"][:20]:
        print(
            "  "
            f"{candidate['address']} width={candidate['width']} "
            f"{candidate['closed']}->{candidate['open']}->{candidate['closed2']} "
            f"score={candidate['score']}"
        )
    return 0


def _load_value_sample(path: Path) -> dict[str, tuple[int, int]]:
    payload = json.loads(path.read_text())
    out: dict[str, tuple[int, int]] = {}
    for entry in payload.get("values") or []:
        if not isinstance(entry, dict) or not entry.get("read_ok"):
            continue
        out[str(entry["address"])] = (
            int(entry.get("width") or 1),
            int(entry.get("value") or 0),
        )
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    pid = args.pid or _find_game_pid()
    if not pid:
        print("Into the Breach process not found.", file=sys.stderr)
        return 2

    lldb_path = args.lldb or shutil.which("lldb")
    if not lldb_path:
        print("lldb not found on PATH.", file=sys.stderr)
        return 2

    candidates_path = Path(args.candidates).expanduser().resolve()
    if not candidates_path.exists():
        print(f"candidate file not found: {candidates_path}", file=sys.stderr)
        return 2

    root = Path(args.output).expanduser().resolve() if args.output else candidates_path.parent
    root.mkdir(parents=True, exist_ok=True)
    samples = [
        root / "pause_probe_validate_current.json",
        root / "pause_probe_validate_toggled.json",
        root / "pause_probe_validate_current2.json",
    ]

    try:
        print(f"PID: {pid}")
        print(f"Candidates: {candidates_path}")
        print("Read 1: current state.")
        _run_lldb_read_values(
            pid=pid,
            candidates_path=candidates_path,
            output_path=samples[0],
            label="current",
            limit=args.limit,
            lldb_path=lldb_path,
        )
        print("Toggling Esc.")
        toggle = _toggle_esc(args.settle_seconds)
        print(f"Esc toggle 1: {toggle.get('status')} {toggle.get('error', '')}")
        if toggle.get("status") != "OK":
            return 3
        print("Read 2: toggled state.")
        _run_lldb_read_values(
            pid=pid,
            candidates_path=candidates_path,
            output_path=samples[1],
            label="toggled",
            limit=args.limit,
            lldb_path=lldb_path,
        )
        print("Toggling Esc back.")
        toggle = _toggle_esc(args.settle_seconds)
        print(f"Esc toggle 2: {toggle.get('status')} {toggle.get('error', '')}")
        if toggle.get("status") != "OK":
            return 3
        print("Read 3: current state again.")
        _run_lldb_read_values(
            pid=pid,
            candidates_path=candidates_path,
            output_path=samples[2],
            label="current2",
            limit=args.limit,
            lldb_path=lldb_path,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    first = _load_value_sample(samples[0])
    second = _load_value_sample(samples[1])
    third = _load_value_sample(samples[2])
    validated: list[dict[str, Any]] = []
    for address, (width, v1) in first.items():
        if address not in second or address not in third:
            continue
        _w2, v2 = second[address]
        _w3, v3 = third[address]
        if v1 == v3 and v1 != v2:
            validated.append({
                "address": address,
                "width": width,
                "current": v1,
                "toggled": v2,
                "current2": v3,
            })

    result = {
        "status": "OK",
        "candidate_file": str(candidates_path),
        "sample_files": [str(p) for p in samples],
        "validated_count": len(validated),
        "validated": validated,
    }
    output_path = root / "pause_probe_validated.json"
    output_path.write_text(json.dumps(result, indent=2))
    print("\n=== PAUSE PROBE VALIDATION ===")
    print(f"validated: {len(validated)} / {len(first)}")
    print(f"saved:     {output_path}")
    for item in validated[:25]:
        print(
            "  "
            f"{item['address']} width={item['width']} "
            f"{item['current']}->{item['toggled']}->{item['current2']}"
        )
    return 0


def _load_value_samples(paths: list[Path]) -> list[dict[str, tuple[int, int]]]:
    return [_load_value_sample(path) for path in paths]


def cmd_validate_cycles(args: argparse.Namespace) -> int:
    pid, lldb_path = _resolve_driver_lldb(args)
    if pid is None or lldb_path is None:
        return 2

    candidates_path = Path(args.candidates).expanduser().resolve()
    if not candidates_path.exists():
        print(f"candidate file not found: {candidates_path}", file=sys.stderr)
        return 2

    toggles = int(args.toggles)
    if toggles < 2:
        print("--toggles must be at least 2", file=sys.stderr)
        return 2
    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path(tempfile.mkdtemp(prefix="itb_pause_cycles_"))
    )
    root.mkdir(parents=True, exist_ok=True)
    control_samples = [
        root / f"pause_control_{idx:02d}.json"
        for idx in range(max(0, int(args.control_reads)))
    ]
    samples = [root / f"pause_cycle_{idx:02d}.json" for idx in range(toggles + 1)]

    try:
        print(f"PID: {pid}")
        print(f"Candidates: {candidates_path}")
        for idx, sample_path in enumerate(control_samples):
            print(f"Control read {idx + 1}/{len(control_samples)}.")
            _run_lldb_read_values(
                pid=pid,
                candidates_path=candidates_path,
                output_path=sample_path,
                label=f"control_{idx:02d}",
                limit=args.limit,
                lldb_path=lldb_path,
            )
            if idx != len(control_samples) - 1 and args.control_settle_seconds > 0:
                time.sleep(args.control_settle_seconds)
        for idx, sample_path in enumerate(samples):
            print(f"Read {idx + 1}/{len(samples)}.")
            _run_lldb_read_values(
                pid=pid,
                candidates_path=candidates_path,
                output_path=sample_path,
                label=f"cycle_{idx:02d}",
                limit=args.limit,
                lldb_path=lldb_path,
            )
            if idx == len(samples) - 1:
                break
            print("Toggling Esc.")
            toggle = _toggle_esc(args.settle_seconds)
            print(f"Esc toggle {idx + 1}: {toggle.get('status')} {toggle.get('error', '')}")
            if toggle.get("status") != "OK":
                return 3
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    controls = _load_value_samples(control_samples)
    loaded = _load_value_samples(samples)
    common_addresses = set(loaded[0])
    for sample in loaded[1:]:
        common_addresses &= set(sample)
    for sample in controls:
        common_addresses &= set(sample)

    validated: list[dict[str, Any]] = []
    for address in sorted(common_addresses, key=lambda raw: int(raw, 16)):
        widths = {loaded[idx][address][0] for idx in range(len(loaded))}
        for control in controls:
            widths.add(control[address][0])
        if len(widths) != 1:
            continue
        control_values = [control[address][1] for control in controls]
        if control_values and len(set(control_values)) != 1:
            continue
        values = [loaded[idx][address][1] for idx in range(len(loaded))]
        even_values = values[0::2]
        odd_values = values[1::2]
        if control_values and even_values[0] != control_values[0]:
            continue
        if len(set(even_values)) == 1 and len(set(odd_values)) == 1 and even_values[0] != odd_values[0]:
            validated.append({
                "address": address,
                "width": widths.pop(),
                "control_value": control_values[0] if control_values else None,
                "even_value": even_values[0],
                "odd_value": odd_values[0],
                "control_values": control_values,
                "values": values,
            })

    result = {
        "status": "OK",
        "candidate_file": str(candidates_path),
        "control_files": [str(path) for path in control_samples],
        "sample_files": [str(path) for path in samples],
        "control_reads": len(control_samples),
        "toggles": toggles,
        "validated_count": len(validated),
        "validated": validated,
    }
    output_path = root / "pause_probe_validated_cycles.json"
    output_path.write_text(json.dumps(result, indent=2))
    print("\n=== PAUSE PROBE CYCLE VALIDATION ===")
    print(f"validated: {len(validated)} / {len(common_addresses)}")
    print(f"saved:     {output_path}")
    for item in validated[:25]:
        values = "->".join(str(value) for value in item["values"])
        print(f"  {item['address']} width={item['width']} {values}")
    return 0


def _resolve_driver_lldb(args: argparse.Namespace) -> tuple[int | None, str | None]:
    pid = args.pid or _find_game_pid()
    if not pid:
        print("Into the Breach process not found.", file=sys.stderr)
        return None, None

    lldb_path = args.lldb or shutil.which("lldb")
    if not lldb_path:
        print("lldb not found on PATH.", file=sys.stderr)
        return None, None
    return pid, lldb_path


def cmd_read_pause(args: argparse.Namespace) -> int:
    pid, lldb_path = _resolve_driver_lldb(args)
    if pid is None or lldb_path is None:
        return 2
    if args.image_offset is None:
        print("No verified default pause offset yet; pass --image-offset.", file=sys.stderr)
        return 2

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path(tempfile.mkdtemp(prefix="itb_pause_read_")) / "pause_read.json"
    )
    try:
        _run_lldb_read_pause_offset(
            pid=pid,
            output_path=output_path,
            label=args.label,
            image_offset=args.image_offset,
            width=args.width,
            open_value=args.open_value,
            lldb_path=lldb_path,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    payload = json.loads(output_path.read_text())
    print("\n=== PAUSE OFFSET READ ===")
    print(f"pid:        {pid}")
    print(f"address:    {payload.get('address')}")
    print(f"offset:     {payload.get('image_offset')}")
    print(f"value:      {payload.get('value')}")
    print(f"open:       {payload.get('pause_menu_open')}")
    print(f"saved:      {output_path}")
    return 0 if payload.get("read_ok") else 5


def _read_pause_value(
    *,
    pid: int,
    output_path: Path,
    label: str,
    image_offset: int,
    width: int,
    open_value: int,
    lldb_path: str,
) -> dict[str, Any]:
    _run_lldb_read_pause_offset(
        pid=pid,
        output_path=output_path,
        label=label,
        image_offset=image_offset,
        width=width,
        open_value=open_value,
        lldb_path=lldb_path,
    )
    return json.loads(output_path.read_text())


def cmd_validate_pause_offset(args: argparse.Namespace) -> int:
    pid, lldb_path = _resolve_driver_lldb(args)
    if pid is None or lldb_path is None:
        return 2
    if args.image_offset is None:
        print("No verified default pause offset yet; pass --image-offset.", file=sys.stderr)
        return 2

    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path(tempfile.mkdtemp(prefix="itb_pause_offset_validate_"))
    )
    root.mkdir(parents=True, exist_ok=True)

    try:
        print(f"PID: {pid}")
        print(f"Image offset: 0x{args.image_offset:x}")
        print("Read 1: current state.")
        current = _read_pause_value(
            pid=pid,
            output_path=root / "pause_offset_current.json",
            label="current",
            image_offset=args.image_offset,
            width=args.width,
            open_value=args.open_value,
            lldb_path=lldb_path,
        )
        print("Toggling Esc.")
        toggle = _toggle_esc(args.settle_seconds)
        print(f"Esc toggle 1: {toggle.get('status')} {toggle.get('error', '')}")
        if toggle.get("status") != "OK":
            return 3
        print("Read 2: toggled state.")
        toggled = _read_pause_value(
            pid=pid,
            output_path=root / "pause_offset_toggled.json",
            label="toggled",
            image_offset=args.image_offset,
            width=args.width,
            open_value=args.open_value,
            lldb_path=lldb_path,
        )
        print("Toggling Esc back.")
        toggle = _toggle_esc(args.settle_seconds)
        print(f"Esc toggle 2: {toggle.get('status')} {toggle.get('error', '')}")
        if toggle.get("status") != "OK":
            return 3
        print("Read 3: current state again.")
        current2 = _read_pause_value(
            pid=pid,
            output_path=root / "pause_offset_current2.json",
            label="current2",
            image_offset=args.image_offset,
            width=args.width,
            open_value=args.open_value,
            lldb_path=lldb_path,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    v1 = current.get("value")
    v2 = toggled.get("value")
    v3 = current2.get("value")
    valid = bool(current.get("read_ok") and toggled.get("read_ok") and current2.get("read_ok"))
    valid = valid and v1 == v3 and v1 != v2
    result = {
        "status": "OK" if valid else "MISMATCH",
        "root": str(root),
        "image_offset": f"0x{args.image_offset:x}",
        "width": args.width,
        "open_value": args.open_value,
        "current": current,
        "toggled": toggled,
        "current2": current2,
    }
    result_path = root / "pause_offset_validation.json"
    result_path.write_text(json.dumps(result, indent=2))

    print("\n=== PAUSE OFFSET VALIDATION ===")
    print(f"status:     {result['status']}")
    print(f"values:     {v1}->{v2}->{v3}")
    print(f"open flags: {current.get('pause_menu_open')}->{toggled.get('pause_menu_open')}->{current2.get('pause_menu_open')}")
    print(f"saved:      {result_path}")
    return 0 if valid else 5


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find memory values that toggle with the ITB pause menu.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="Capture closed/open/closed samples")
    p_run.add_argument("--pid", type=int, default=None)
    p_run.add_argument("--output", default=None)
    p_run.add_argument("--lldb", default=None)
    p_run.add_argument("--max-region", type=int, default=DEFAULT_MAX_REGION)
    p_run.add_argument("--max-total", type=int, default=DEFAULT_MAX_TOTAL)
    p_run.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    p_run.add_argument("--settle-seconds", type=float, default=0.35)
    p_run.add_argument(
        "--no-toggle",
        action="store_true",
        help="Do not press Esc between samples; useful for manual testing",
    )
    p_run.set_defaults(func=cmd_run)
    p_validate = sub.add_parser(
        "validate",
        help="Re-read candidate addresses across another Esc cycle",
    )
    p_validate.add_argument("candidates")
    p_validate.add_argument("--pid", type=int, default=None)
    p_validate.add_argument("--output", default=None)
    p_validate.add_argument("--lldb", default=None)
    p_validate.add_argument("--limit", type=int, default=DEFAULT_MAX_CANDIDATES)
    p_validate.add_argument("--settle-seconds", type=float, default=0.35)
    p_validate.set_defaults(func=cmd_validate)
    p_validate_cycles = sub.add_parser(
        "validate-cycles",
        help="Re-read candidates across multiple Esc toggles and keep parity-stable values",
    )
    p_validate_cycles.add_argument("candidates")
    p_validate_cycles.add_argument("--pid", type=int, default=None)
    p_validate_cycles.add_argument("--output", default=None)
    p_validate_cycles.add_argument("--lldb", default=None)
    p_validate_cycles.add_argument("--limit", type=int, default=DEFAULT_MAX_CANDIDATES)
    p_validate_cycles.add_argument("--toggles", type=int, default=6)
    p_validate_cycles.add_argument("--settle-seconds", type=float, default=0.6)
    p_validate_cycles.add_argument("--control-reads", type=int, default=0)
    p_validate_cycles.add_argument("--control-settle-seconds", type=float, default=0.6)
    p_validate_cycles.set_defaults(func=cmd_validate_cycles)
    p_read_pause = sub.add_parser(
        "read-pause",
        help="Read the current pause-menu field by module-relative offset",
    )
    p_read_pause.add_argument("--pid", type=int, default=None)
    p_read_pause.add_argument("--output", default=None)
    p_read_pause.add_argument("--lldb", default=None)
    p_read_pause.add_argument("--label", default="current")
    p_read_pause.add_argument("--image-offset", type=lambda raw: int(raw, 0), default=DEFAULT_PAUSE_IMAGE_OFFSET)
    p_read_pause.add_argument("--width", type=int, default=1)
    p_read_pause.add_argument("--open-value", type=lambda raw: int(raw, 0), default=DEFAULT_PAUSE_OPEN_VALUE)
    p_read_pause.set_defaults(func=cmd_read_pause)
    p_validate_offset = sub.add_parser(
        "validate-pause-offset",
        help="Read the pause offset across an Esc open/close cycle",
    )
    p_validate_offset.add_argument("--pid", type=int, default=None)
    p_validate_offset.add_argument("--output", default=None)
    p_validate_offset.add_argument("--lldb", default=None)
    p_validate_offset.add_argument("--image-offset", type=lambda raw: int(raw, 0), default=DEFAULT_PAUSE_IMAGE_OFFSET)
    p_validate_offset.add_argument("--width", type=int, default=1)
    p_validate_offset.add_argument("--open-value", type=lambda raw: int(raw, 0), default=DEFAULT_PAUSE_OPEN_VALUE)
    p_validate_offset.add_argument("--settle-seconds", type=float, default=0.35)
    p_validate_offset.set_defaults(func=cmd_validate_pause_offset)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
