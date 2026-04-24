#!/usr/bin/env python3
"""Poll profile_Alpha/saveData.lua and log when aiSeed or iCurrentTurn change.

Purpose: discriminate WHEN the game actually writes aiSeed during a turn.
Run in a separate terminal before clicking End Turn:

    python3 scripts/watch_save_file.py

Output (appended): recordings/save_timing.jsonl — one line per observed change:
    {"wallclock_ms": int, "ai_seed": int, "turn": int, "file_mtime": float}

The very first observation is always emitted (baseline). Subsequent lines only
append when ai_seed or turn differs from the last emitted record.

Stops on Ctrl-C. Exit code 0 on clean stop.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

SAVE_PATH = Path(
    "/Users/aircow/Library/Application Support/IntoTheBreach/profile_Alpha/saveData.lua"
)
OUT_PATH = Path(__file__).resolve().parent.parent / "recordings" / "save_timing.jsonl"
POLL_INTERVAL_S = 0.25  # 250 ms — task-spec minimum is 50 ms, max sensible is ~1 s.
RETRY_DELAY_S = 0.05    # 50 ms retry if parse fails (file may be mid-write).

# Find EVERY region block, brace-walk it, then pick the one whose iState==0
# (the mission currently in combat). Region assignment changes between
# missions — hardcoding region1 only works for the first run. Lua saves use
# balanced `{...}` so a simple depth counter is enough.
_REGION_HEAD = re.compile(r'\["(region\d+)"\]\s*=\s*\{')
_AI_SEED = re.compile(r'\["aiSeed"\]\s*=\s*(-?\d+)')
_TURN = re.compile(r'\["iCurrentTurn"\]\s*=\s*(-?\d+)')
_STATE = re.compile(r'\["iState"\]\s*=\s*(-?\d+)')


def _walk_block(text: str, start: int) -> int | None:
    """Return the index just past the closing `}` of the block starting at
    `start` (which must point at position just after the opening `{`)."""
    depth = 1
    i = start
    n = len(text)
    while i < n and depth > 0:
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None  # never balanced — mid-write


def _extract_active_region_block(text: str) -> tuple[str, str] | None:
    """Scan every region and return (region_key, block_contents) for the
    region whose iState==0 (the mission currently in combat). Missions that
    are scouted but not yet entered have iState==4. If no region is active,
    returns None.
    """
    for m in _REGION_HEAD.finditer(text):
        region_key = m.group(1)
        end = _walk_block(text, m.end())
        if end is None:
            continue
        block = text[m.end():end - 1]  # drop the closing `}`
        state_match = _STATE.search(block)
        if state_match and int(state_match.group(1)) == 0:
            return region_key, block
    return None


def _parse(text: str) -> tuple[str, int, int] | None:
    active = _extract_active_region_block(text)
    if active is None:
        return None
    region_key, block = active
    s = _AI_SEED.search(block)
    t = _TURN.search(block)
    if not s or not t:
        return None
    return region_key, int(s.group(1)), int(t.group(1))


def _read_and_parse(path: Path) -> tuple[str, int, int, float] | None:
    """Read + parse with one retry if parse fails (game may be mid-write)."""
    for attempt in range(2):
        try:
            mtime = path.stat().st_mtime
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None
        parsed = _parse(text)
        if parsed is not None:
            return parsed[0], parsed[1], parsed[2], mtime
        if attempt == 0:
            time.sleep(RETRY_DELAY_S)
    return None


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SAVE_PATH.exists():
        print(f"save file not found: {SAVE_PATH}", file=sys.stderr)
        return 1

    print(f"watching: {SAVE_PATH}", file=sys.stderr)
    print(f"writing:  {OUT_PATH}", file=sys.stderr)
    print("Ctrl-C to stop.", file=sys.stderr)

    last_seed: int | None = None
    last_turn: int | None = None
    last_region: str | None = None
    last_mtime: float | None = None

    try:
        with OUT_PATH.open("a", buffering=1) as out:  # line-buffered
            while True:
                # Skip re-read if mtime hasn't changed since last poll.
                try:
                    mtime = SAVE_PATH.stat().st_mtime
                except FileNotFoundError:
                    time.sleep(POLL_INTERVAL_S)
                    continue
                if last_mtime is not None and mtime == last_mtime and last_seed is not None:
                    time.sleep(POLL_INTERVAL_S)
                    continue

                rec = _read_and_parse(SAVE_PATH)
                if rec is None:
                    time.sleep(POLL_INTERVAL_S)
                    continue
                region_key, ai_seed, turn, file_mtime = rec
                last_mtime = file_mtime

                changed = (
                    ai_seed != last_seed
                    or turn != last_turn
                    or region_key != last_region
                )
                if not changed:
                    time.sleep(POLL_INTERVAL_S)
                    continue

                wallclock_ms = int(time.time() * 1000)
                line = json.dumps({
                    "wallclock_ms": wallclock_ms,
                    "region": region_key,
                    "ai_seed": ai_seed,
                    "turn": turn,
                    "file_mtime": file_mtime,
                })
                out.write(line + "\n")

                # Stderr real-time feedback.
                if last_turn is not None and turn != last_turn:
                    print(
                        f"[{wallclock_ms}] TURN ADVANCED {last_turn} -> {turn} "
                        f"(aiSeed {last_seed} -> {ai_seed})",
                        file=sys.stderr,
                    )
                elif last_seed is None:
                    print(
                        f"[{wallclock_ms}] baseline turn={turn} aiSeed={ai_seed}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[{wallclock_ms}] SEED CHANGED turn={turn} "
                        f"aiSeed {last_seed} -> {ai_seed}",
                        file=sys.stderr,
                    )

                last_seed = ai_seed
                last_turn = turn
                last_region = region_key
                time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nstopped.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
