"""
LLDB-based memory scanner for Into the Breach.
LLDB has the com.apple.security.cs.debugger entitlement, so it can
attach to the game without disabling SIP.

Usage:
    lldb -p $(pgrep -f "Into the Breach") -o "command script import /path/to/lldb_scan.py" -o "itb_scan" -o "quit"

Or interactively:
    lldb -p $(pgrep -f "Into the Breach")
    (lldb) command script import /path/to/lldb_scan.py
    (lldb) itb_scan
"""

import lldb
import json
import struct
import time
import os

TERRAIN_MAP = {
    "ground": 0, "building": 1, "rubble": 2, "water": 3,
    "mountain": 4, "lava": 5, "forest": 6, "sand": 7,
    "ice": 8, "chasm": 9,
}


def get_terrain_from_bridge():
    """Read current terrain from bridge state JSON."""
    try:
        with open("/tmp/itb_state.json", "r") as f:
            state = json.load(f)
        tiles = state.get("tiles", [])
        if len(tiles) != 64:
            return None
        terrain = bytearray(64)
        for tile in tiles:
            x, y = tile["x"], tile["y"]
            t = TERRAIN_MAP.get(tile.get("terrain", "ground"), 0)
            terrain[y * 8 + x] = t
        return bytes(terrain)
    except Exception as e:
        print(f"Error reading bridge state: {e}")
        return None


def read_process_memory(process, addr, size):
    """Read bytes from the target process."""
    error = lldb.SBError()
    data = process.ReadMemory(addr, size, error)
    if error.Success():
        return data
    return None


def scan_regions(process, pattern, max_matches=10):
    """Scan all memory regions for a byte pattern."""
    matches = []
    total_scanned = 0
    regions = 0

    target = process.GetTarget()
    # Enumerate memory regions using SBMemoryRegionInfo
    region_list = process.GetMemoryRegions()
    num_regions = region_list.GetSize()

    print(f"  Enumerating {num_regions} memory regions...")

    for i in range(num_regions):
        region = lldb.SBMemoryRegionInfo()
        region_list.GetMemoryRegionAtIndex(i, region)

        # Only scan readable+writable regions (heap)
        if not region.IsReadable() or not region.IsWritable():
            continue

        start = region.GetRegionBase()
        end = region.GetRegionEnd()
        size = end - start

        # Skip tiny and huge regions
        if size < len(pattern) or size > 200 * 1024 * 1024:
            continue

        # Read in chunks to avoid huge allocations
        chunk_size = min(size, 4 * 1024 * 1024)  # 4MB chunks
        offset = 0
        while offset < size:
            read_size = min(chunk_size, size - offset)
            data = read_process_memory(process, start + offset, read_size)
            if data is None:
                break

            regions += 1
            total_scanned += len(data)

            # Search for pattern
            search_offset = 0
            while search_offset <= len(data) - len(pattern):
                idx = data.find(pattern, search_offset)
                if idx == -1:
                    break
                match_addr = start + offset + idx
                matches.append(match_addr)
                print(f"  MATCH at 0x{match_addr:016x}")
                if len(matches) >= max_matches:
                    return matches, total_scanned
                search_offset = idx + 1

            offset += read_size - len(pattern) + 1  # overlap for split matches

    print(f"  Scanned {regions} chunks, {total_scanned / 1024 / 1024:.1f} MB total")
    return matches, total_scanned


def do_scan(debugger, command, result, internal_dict):
    """LLDB command: scan for Board terrain pattern in game memory."""
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()

    if not process or not process.IsValid():
        print("No valid process. Attach to the game first.")
        return

    # Ensure process is stopped (LLDB pauses on attach)
    state = process.GetState()
    print(f"Process state: {state} (stopped={state == lldb.eStateStopped})")

    terrain = get_terrain_from_bridge()
    if terrain is None:
        print("Could not read terrain from bridge state. Is the game in a mission?")
        return

    print(f"Terrain (1-byte): {terrain.hex()}")

    # Try different strides
    strides = [
        (1, "uint8"),
        (4, "int32"),
        (2, "int16"),
    ]

    for stride, desc in strides:
        if stride == 1:
            pattern = terrain
        elif stride == 2:
            pattern = b"".join(struct.pack("<H", b) for b in terrain)
        elif stride == 4:
            pattern = b"".join(struct.pack("<i", b) for b in terrain)

        print(f"\nSearching for {desc} pattern ({len(pattern)} bytes)...")
        t0 = time.time()
        matches, scanned = scan_regions(process, pattern)
        elapsed = time.time() - t0
        print(f"  {len(matches)} matches in {elapsed:.2f}s")

        if matches:
            result_data = {
                "stride": stride,
                "type": desc,
                "terrain_addr": f"0x{matches[0]:016x}",
                "all_matches": [f"0x{a:016x}" for a in matches],
            }
            with open("/tmp/itb_board_scan.json", "w") as f:
                json.dump(result_data, f, indent=2)
            print(f"\nSaved scan results to /tmp/itb_board_scan.json")

            # Dump memory around first match
            center = matches[0]
            before, after = 2048, 4096
            dump_data = read_process_memory(process, center - before, before + after)
            if dump_data:
                with open("/tmp/itb_board_dump.bin", "wb") as f:
                    f.write(dump_data)
                meta = {
                    "center": f"0x{center:016x}",
                    "start": f"0x{center - before:016x}",
                    "size": before + after,
                }
                with open("/tmp/itb_board_dump.bin.meta.json", "w") as f:
                    json.dump(meta, f, indent=2)
                print(f"Dumped {len(dump_data)} bytes around 0x{center:016x}")

            # Resume the process so the game doesn't freeze
            print("\nResuming game process...")
            process.Continue()
            return

    print("\nNo terrain pattern found at any stride.")
    process.Continue()


def do_dump(debugger, command, result, internal_dict):
    """LLDB command: dump memory around previously found Board address."""
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()

    try:
        with open("/tmp/itb_board_scan.json") as f:
            scan = json.load(f)
    except FileNotFoundError:
        print("No scan result. Run itb_scan first.")
        return

    addr = int(scan["terrain_addr"], 16)
    label = command.strip() if command.strip() else "dump"
    outfile = f"/tmp/itb_board_{label}.bin"

    before, after = 2048, 4096
    data = read_process_memory(process, addr - before, before + after)
    if data:
        with open(outfile, "wb") as f:
            f.write(data)
        print(f"Saved {len(data)} bytes to {outfile}")
    else:
        print(f"Failed to read memory at 0x{addr:016x}")

    process.Continue()


def __lldb_init_module(debugger, internal_dict):
    """Register LLDB commands when the script is imported."""
    debugger.HandleCommand(
        'command script add -f lldb_scan.do_scan itb_scan'
    )
    debugger.HandleCommand(
        'command script add -f lldb_scan.do_dump itb_dump'
    )
    print("ITB memory scanner loaded. Commands: itb_scan, itb_dump <label>")
