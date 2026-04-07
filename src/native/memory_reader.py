"""
macOS process memory reader for Into the Breach.
Uses Mach APIs (task_for_pid + mach_vm_read) via ctypes —
the macOS equivalent of the Demon Bluff solver's ReadProcessMemory.

Usage:
    sudo python3 memory_reader.py scan          # Find Board in game memory
    sudo python3 memory_reader.py dump           # Dump memory around Board
    sudo python3 memory_reader.py diff <a> <b>   # Diff two dumps to find highlight offset
"""

from __future__ import annotations

import ctypes
import ctypes.util
import struct
import subprocess
import sys
import json
import os
import time
from typing import Optional, List, Dict, Tuple

# ---------------------------------------------------------------------------
# macOS Mach API bindings via ctypes
# ---------------------------------------------------------------------------

libc = ctypes.CDLL(ctypes.util.find_library("c"))

# Types
mach_port_t = ctypes.c_uint32
kern_return_t = ctypes.c_int
vm_address_t = ctypes.c_uint64
vm_size_t = ctypes.c_uint64
vm_offset_t = ctypes.c_uint64
natural_t = ctypes.c_uint32
mach_msg_type_number_t = ctypes.c_uint32
vm_prot_t = ctypes.c_int
vm_inherit_t = ctypes.c_uint32
boolean_t = ctypes.c_int
memory_object_name_t = ctypes.c_uint32
vm_behavior_t = ctypes.c_int

# VM_REGION_BASIC_INFO_64 struct
class vm_region_basic_info_64(ctypes.Structure):
    _fields_ = [
        ("protection", vm_prot_t),
        ("max_protection", vm_prot_t),
        ("inheritance", vm_inherit_t),
        ("shared", boolean_t),
        ("reserved", boolean_t),
        ("offset", vm_offset_t),
        ("behavior", vm_behavior_t),
        ("user_wired_count", ctypes.c_ushort),
    ]

VM_REGION_BASIC_INFO_64 = 9
VM_REGION_BASIC_INFO_64_COUNT = ctypes.sizeof(vm_region_basic_info_64) // ctypes.sizeof(natural_t)
VM_PROT_READ = 1
VM_PROT_WRITE = 2
KERN_SUCCESS = 0

# Function signatures
libc.mach_task_self.restype = mach_port_t

libc.task_for_pid.argtypes = [mach_port_t, ctypes.c_int, ctypes.POINTER(mach_port_t)]
libc.task_for_pid.restype = kern_return_t

libc.mach_vm_region.argtypes = [
    mach_port_t,                              # target_task
    ctypes.POINTER(vm_address_t),             # address (in/out)
    ctypes.POINTER(vm_size_t),                # size (out)
    ctypes.c_int,                             # flavor
    ctypes.POINTER(vm_region_basic_info_64),  # info (out)
    ctypes.POINTER(mach_msg_type_number_t),   # info_count (in/out)
    ctypes.POINTER(mach_port_t),              # object_name (out)
]
libc.mach_vm_region.restype = kern_return_t

libc.mach_vm_read.argtypes = [
    mach_port_t,                              # target_task
    vm_address_t,                             # address
    vm_size_t,                                # size
    ctypes.POINTER(vm_address_t),             # data (out)
    ctypes.POINTER(mach_msg_type_number_t),   # data_count (out)
]
libc.mach_vm_read.restype = kern_return_t

libc.mach_vm_deallocate.argtypes = [mach_port_t, vm_address_t, vm_size_t]
libc.mach_vm_deallocate.restype = kern_return_t


# ---------------------------------------------------------------------------
# Process discovery
# ---------------------------------------------------------------------------

def find_game_pid() -> int | None:
    """Find the Into the Breach process ID."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "Into the Breach"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split("\n")
        pids = [int(p) for p in pids if p.strip()]
        return pids[0] if pids else None
    except Exception:
        return None


def get_task_port(pid: int) -> mach_port_t | None:
    """Get the Mach task port for a process. Requires root."""
    task = mach_port_t()
    self_task = libc.mach_task_self()
    kr = libc.task_for_pid(self_task, pid, ctypes.byref(task))
    if kr != KERN_SUCCESS:
        print(f"task_for_pid failed: kern_return={kr}")
        print("  - Are you running as root? (sudo)")
        print("  - Is SIP disabled? (csrutil status)")
        return None
    return task


# ---------------------------------------------------------------------------
# Memory region enumeration
# ---------------------------------------------------------------------------

def enumerate_regions(task: mach_port_t, readable_writable_only: bool = True):
    """Yield (address, size, protection) for each VM region."""
    address = vm_address_t(0)
    size = vm_size_t(0)
    info = vm_region_basic_info_64()
    info_count = mach_msg_type_number_t(VM_REGION_BASIC_INFO_64_COUNT)
    obj_name = mach_port_t(0)

    while True:
        info_count.value = VM_REGION_BASIC_INFO_64_COUNT
        kr = libc.mach_vm_region(
            task,
            ctypes.byref(address),
            ctypes.byref(size),
            VM_REGION_BASIC_INFO_64,
            ctypes.byref(info),
            ctypes.byref(info_count),
            ctypes.byref(obj_name),
        )
        if kr != KERN_SUCCESS:
            break  # No more regions

        prot = info.protection
        if not readable_writable_only or (prot & VM_PROT_READ and prot & VM_PROT_WRITE):
            yield address.value, size.value, prot

        address.value += size.value


# ---------------------------------------------------------------------------
# Memory reading
# ---------------------------------------------------------------------------

def read_memory(task: mach_port_t, address: int, size: int) -> bytes | None:
    """Read `size` bytes from `address` in the target task."""
    data_ptr = vm_address_t(0)
    data_count = mach_msg_type_number_t(0)

    kr = libc.mach_vm_read(
        task,
        vm_address_t(address),
        vm_size_t(size),
        ctypes.byref(data_ptr),
        ctypes.byref(data_count),
    )
    if kr != KERN_SUCCESS:
        return None

    # Copy data from the mapped page
    buf = ctypes.string_at(data_ptr.value, data_count.value)

    # Deallocate the mapped memory
    libc.mach_vm_deallocate(libc.mach_task_self(), data_ptr, vm_size_t(data_count.value))

    return buf


# ---------------------------------------------------------------------------
# Pattern scanning
# ---------------------------------------------------------------------------

def build_terrain_patterns(terrain_1byte: bytes) -> list[tuple[bytes, int, str]]:
    """
    Build search patterns for the 64-tile terrain array at different strides.
    C++ enums are typically 4 bytes, but could be 1 or 2.
    Returns list of (pattern_bytes, stride, description).
    """
    patterns = []

    # 1-byte stride (uint8_t terrain[64])
    patterns.append((terrain_1byte, 1, "uint8"))

    # 4-byte stride (int terrain[64])  — most likely for C++ enum
    pat4 = b""
    for b in terrain_1byte:
        pat4 += struct.pack("<i", b)
    patterns.append((pat4, 4, "int32"))

    # 2-byte stride (int16_t terrain[64])
    pat2 = b""
    for b in terrain_1byte:
        pat2 += struct.pack("<H", b)
    patterns.append((pat2, 2, "int16"))

    return patterns


def scan_for_pattern(task: mach_port_t, pattern: bytes, max_matches: int = 10) -> list[int]:
    """Scan all readable+writable regions for the given byte pattern."""
    matches = []
    total_scanned = 0
    regions_scanned = 0

    for addr, size, prot in enumerate_regions(task):
        # Skip very small or very large regions
        if size < len(pattern) or size > 500 * 1024 * 1024:
            continue

        data = read_memory(task, addr, size)
        if data is None:
            continue

        regions_scanned += 1
        total_scanned += len(data)

        # Search for pattern in this region
        offset = 0
        while offset <= len(data) - len(pattern):
            idx = data.find(pattern, offset)
            if idx == -1:
                break
            match_addr = addr + idx
            matches.append(match_addr)
            if len(matches) >= max_matches:
                return matches
            offset = idx + 1

    print(f"  Scanned {regions_scanned} regions, {total_scanned / 1024 / 1024:.1f} MB")
    return matches


# ---------------------------------------------------------------------------
# Board discovery
# ---------------------------------------------------------------------------

def get_terrain_from_bridge() -> bytes | None:
    """Read the current terrain layout from the bridge state file."""
    try:
        with open("/tmp/itb_state.json", "r") as f:
            state = json.load(f)
        tiles = state.get("tiles", [])
        if len(tiles) != 64:
            print(f"  Warning: expected 64 tiles, got {len(tiles)}")
            return None

        # Build 1-byte terrain array in row-major order (y=0..7, x=0..7)
        terrain_map = {
            "ground": 0, "building": 1, "rubble": 2, "water": 3,
            "mountain": 4, "lava": 5, "forest": 6, "sand": 7,
            "ice": 8, "chasm": 9,
        }
        terrain = bytearray(64)
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            t = terrain_map.get(tile.get("terrain", "ground"), 0)
            terrain[y * 8 + x] = t
        return bytes(terrain)
    except Exception as e:
        print(f"  Error reading bridge state: {e}")
        return None


def find_board(task: mach_port_t) -> dict | None:
    """
    Find the Board's terrain array in game memory.
    Returns dict with match info or None.
    """
    terrain = get_terrain_from_bridge()
    if terrain is None:
        print("Could not read terrain from bridge state.")
        return None

    print(f"Terrain pattern (hex): {terrain.hex()}")
    patterns = build_terrain_patterns(terrain)

    for pattern, stride, desc in patterns:
        print(f"\nSearching for {desc} pattern ({len(pattern)} bytes)...")
        t0 = time.time()
        matches = scan_for_pattern(task, pattern)
        elapsed = time.time() - t0
        print(f"  Found {len(matches)} matches in {elapsed:.2f}s")

        if matches:
            for addr in matches:
                print(f"  Match at: 0x{addr:016x}")
            return {
                "stride": stride,
                "type": desc,
                "terrain_addr": matches[0],
                "all_matches": [f"0x{a:016x}" for a in matches],
                "terrain_pattern": terrain.hex(),
            }

    print("\nNo matches found for any stride.")
    return None


# ---------------------------------------------------------------------------
# Memory dumping
# ---------------------------------------------------------------------------

def dump_around(task: mach_port_t, center: int, before: int = 1024, after: int = 2048,
                output: str = "/tmp/itb_board_dump.bin"):
    """Dump memory around an address to a file."""
    start = center - before
    size = before + after
    data = read_memory(task, start, size)
    if data:
        with open(output, "wb") as f:
            f.write(data)
        print(f"Dumped {len(data)} bytes (0x{start:x} - 0x{start+size:x}) to {output}")
        # Also write metadata
        meta = {
            "center": f"0x{center:016x}",
            "start": f"0x{start:016x}",
            "size": size,
            "before": before,
            "after": after,
        }
        with open(output + ".meta.json", "w") as f:
            json.dump(meta, f, indent=2)
    else:
        print(f"Failed to read memory at 0x{start:x}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_scan():
    """Find the Board terrain array in game memory."""
    pid = find_game_pid()
    if not pid:
        print("Into the Breach not running.")
        return
    print(f"Game PID: {pid}")

    task = get_task_port(pid)
    if not task:
        return

    result = find_board(task)
    if result:
        print(f"\nBoard terrain found!")
        print(json.dumps(result, indent=2))
        with open("/tmp/itb_board_scan.json", "w") as f:
            json.dump(result, f, indent=2)


def cmd_dump():
    """Dump memory around the Board (must run scan first)."""
    pid = find_game_pid()
    if not pid:
        print("Into the Breach not running.")
        return

    task = get_task_port(pid)
    if not task:
        return

    # Load previous scan result
    try:
        with open("/tmp/itb_board_scan.json") as f:
            scan = json.load(f)
    except FileNotFoundError:
        print("No scan result found. Run 'scan' first.")
        return

    terrain_addr = int(scan["terrain_addr"], 16)
    print(f"Dumping around terrain at 0x{terrain_addr:016x}...")
    dump_around(task, terrain_addr, before=2048, after=4096)


def cmd_regions():
    """List all memory regions of the game process."""
    pid = find_game_pid()
    if not pid:
        print("Into the Breach not running.")
        return
    print(f"Game PID: {pid}")

    task = get_task_port(pid)
    if not task:
        return

    total = 0
    count = 0
    for addr, size, prot in enumerate_regions(task, readable_writable_only=False):
        prot_str = ""
        prot_str += "r" if prot & 1 else "-"
        prot_str += "w" if prot & 2 else "-"
        prot_str += "x" if prot & 4 else "-"
        print(f"  0x{addr:016x} - 0x{addr+size:016x}  {size:>12,} bytes  {prot_str}")
        total += size
        count += 1

    print(f"\n{count} regions, {total / 1024 / 1024:.1f} MB total")


def cmd_diff(file_a: str, file_b: str):
    """Diff two memory dumps to find changed bytes."""
    with open(file_a, "rb") as f:
        a = f.read()
    with open(file_b, "rb") as f:
        b = f.read()

    size = min(len(a), len(b))
    diffs = []
    for i in range(size):
        if a[i] != b[i]:
            diffs.append((i, a[i], b[i]))

    print(f"Compared {size} bytes, {len(diffs)} differences:")
    for offset, va, vb in diffs[:100]:
        print(f"  +0x{offset:04x}: {va:02x} -> {vb:02x}")

    if len(diffs) > 100:
        print(f"  ... and {len(diffs) - 100} more")


def main():
    if len(sys.argv) < 2:
        print("Usage: sudo python3 memory_reader.py <command>")
        print("Commands: scan, dump, regions, diff <a> <b>")
        return

    cmd = sys.argv[1]
    if cmd == "scan":
        cmd_scan()
    elif cmd == "dump":
        cmd_dump()
    elif cmd == "regions":
        cmd_regions()
    elif cmd == "diff" and len(sys.argv) >= 4:
        cmd_diff(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
