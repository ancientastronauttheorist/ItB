"""Bridge IPC protocol — file paths, polling, and synchronization.

The Lua bridge communicates via files in /tmp/:
  - itb_state.json: Game state (Lua writes, Python reads)
  - itb_cmd.txt:    Commands (Python writes, Lua reads)
  - itb_ack.txt:    Acknowledgments (Lua writes, Python reads)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

STATE_FILE = Path("/tmp/itb_state.json")
CMD_FILE = Path("/tmp/itb_cmd.txt")
CMD_TMP = Path("/tmp/itb_cmd.txt.tmp")
ACK_FILE = Path("/tmp/itb_ack.txt")
LOG_FILE = Path("/tmp/itb_bridge.log")
HEARTBEAT_FILE = Path("/tmp/itb_bridge_heartbeat")

# State file must be newer than this many seconds
STALENESS_THRESHOLD = 300.0  # 5 minutes

# Command sequence counter for ACK correlation
_seq_counter = 0


class BridgeError(Exception):
    """Raised when the bridge returns an ERROR ACK."""
    pass


def is_bridge_active() -> bool:
    """Check if the Lua bridge is running.

    Checks two things:
    1. Bridge log file exists (written on game startup)
    2. State file exists (written when in a mission)
    """
    if not LOG_FILE.exists():
        return False
    if not STATE_FILE.exists():
        return False
    # State file must not be ancient unless the heartbeat proves the Lua
    # bridge is still ticking. On island-map screens the bridge may not dump
    # combat JSON until prompted, but a fresh heartbeat means refresh can work.
    age = time.time() - STATE_FILE.stat().st_mtime
    if age < STALENESS_THRESHOLD:
        return True
    return is_bridge_alive(max_stale_sec=5.0)


def is_bridge_alive(max_stale_sec: float = 5.0) -> bool:
    """Check if the Lua bridge heartbeat is fresh (game loop is ticking).

    The heartbeat file is written every BaseUpdate tick by modloader.lua.
    If it's stale, the bridge is stuck or the game has closed.
    """
    try:
        if not HEARTBEAT_FILE.exists():
            return False
        age = time.time() - HEARTBEAT_FILE.stat().st_mtime
        return age < max_stale_sec
    except OSError:
        return False


def refresh_bridge_state() -> bool:
    """Request a fresh state dump from the bridge.

    Sends a no-op LUA command which triggers dump_state() as a side effect.
    Returns True if state was refreshed.
    """
    write_command("LUA return 'refresh'")
    try:
        wait_for_ack(timeout=5.0)
        return True
    except (TimeoutError, BridgeError):
        return False


def read_state() -> dict | None:
    """Read the current game state JSON. Returns None if unavailable."""
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def write_command(cmd: str) -> None:
    """Write a command with sequence ID (atomic via tmp+rename).

    Prepends a sequence ID (#NNN) for ACK correlation.
    Clears any stale ACK file first to prevent reading the previous
    command's response as this command's ACK (race condition fix).
    """
    global _seq_counter

    # Clear stale ACK to prevent reading previous command's response
    try:
        ACK_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    time.sleep(0.05)  # brief settle time

    _seq_counter += 1
    full_cmd = f"#{_seq_counter} {cmd}"

    with open(CMD_TMP, "w") as f:
        f.write(full_cmd)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(CMD_TMP), str(CMD_FILE))


def wait_for_ack(timeout: float = 10.0) -> str:
    """Poll for ACK file. Returns content after stripping sequence ID.

    Two-tier timeout: at 20s, checks the bridge heartbeat. If the heartbeat
    is stale (Lua stopped ticking), fails fast. If fresh, keeps waiting up
    to the full timeout (legitimate slow animations can take 30s+).

    Raises TimeoutError if no ACK within timeout.
    Raises BridgeError if ACK indicates an error.
    """
    deadline = time.time() + timeout
    heartbeat_check_at = time.time() + 20.0
    heartbeat_checked = False
    while time.time() < deadline:
        if ACK_FILE.exists():
            try:
                content = ACK_FILE.read_text().strip()
                ACK_FILE.unlink()

                # Strip sequence ID prefix (#NNN)
                if content.startswith("#"):
                    space_idx = content.find(" ")
                    if space_idx > 0:
                        seq_str = content[1:space_idx]
                        content = content[space_idx + 1:]
                        # Verify sequence match (skip stale ACKs)
                        try:
                            if int(seq_str) != _seq_counter:
                                continue
                        except ValueError:
                            pass

                # Check for error
                if content.startswith("ERROR"):
                    raise BridgeError(content)

                return content
            except BridgeError:
                raise
            except IOError:
                pass
        # Two-tier: early fail if bridge heartbeat is stale
        if not heartbeat_checked and time.time() >= heartbeat_check_at:
            heartbeat_checked = True
            if not is_bridge_alive(max_stale_sec=5.0):
                raise TimeoutError(
                    f"Bridge heartbeat stale after 20s — Lua stopped ticking"
                )
        time.sleep(0.1)
    raise TimeoutError(f"Bridge ACK timeout after {timeout:.0f}s")


def wait_for_fresh_state(timeout: float = 10.0) -> dict | None:
    """Wait for a state file newer than now. Returns parsed JSON or None."""
    start = time.time()
    deadline = start + timeout
    while time.time() < deadline:
        if STATE_FILE.exists():
            mtime = STATE_FILE.stat().st_mtime
            if mtime >= start:
                try:
                    with open(STATE_FILE) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        time.sleep(0.2)
    return None
