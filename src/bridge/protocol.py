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

# State file must be newer than this many seconds to be considered active
STALENESS_THRESHOLD = 30.0


def is_bridge_active() -> bool:
    """Check if the Lua bridge is running (state file exists and is recent)."""
    if not STATE_FILE.exists():
        return False
    age = time.time() - STATE_FILE.stat().st_mtime
    return age < STALENESS_THRESHOLD


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
    """Write a command to the command file (atomic via tmp+rename)."""
    with open(CMD_TMP, "w") as f:
        f.write(cmd)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(CMD_TMP), str(CMD_FILE))


def wait_for_ack(timeout: float = 10.0) -> str:
    """Poll for acknowledgment file. Returns ack content or raises TimeoutError."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ACK_FILE.exists():
            try:
                content = ACK_FILE.read_text().strip()
                ACK_FILE.unlink()
                return content
            except IOError:
                pass
        time.sleep(0.1)
    raise TimeoutError(f"Bridge ACK timeout after {timeout}s")


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
