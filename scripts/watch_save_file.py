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

# Locate `["region1"] = {` then brace-walk. Lua saves use balanced `{...}` so a
# simple depth counter is enough. We only need the *contents* of that block,
# then can sub-match aiSeed / iCurrentTurn inside.
_REGION1_HEAD = re.compile(r'\["region1"\]\s*=\s*\{')
_AI_SEED = re.compile(r'\["aiSeed"\]\s*=\s*(-?\d+)')
_TURN = re.compile(r'\["iCurrentTurn"\]\s*=\s*(-?\d+)')


def _extract_region1_block(text: str) -> str | None:
    """Return the brace-balanced contents of the `["region1"] = {...}` block.

    Returns None if `region1` isn't present or braces never balance (partial
    write). Uses a simple depth counter — Lua saveData.lua doesn't embed `{`
    inside string literals in this region, so we don't need a full parser.
    """
    m = _REGION1_HEAD.search(text)
    if not m:
        return None
    start = m.end()  # position just after the opening `{`
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
                return text[start:i]
        i += 1
    return None  # never balanced — mid-write


def _parse(text: str) -> tuple[int, int] | None:
    block = _extract_region1_block(text)
    if block is None:
        return None
    s = _AI_SEED.search(block)
    t = _TURN.search(block)
    if not s or not t:
        return None
    return int(s.group(1)), int(t.group(1))


def _read_and_parse(path: Path) -> tuple[int, int, float] | None:
    """Read + parse with one retry if parse fails (game may be mid-write)."""
    for attempt in range(2):
        try:
            mtime = path.stat().st_mtime
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None
        parsed = _parse(text)
        if parsed is not None:
            return parsed[0], parsed[1], mtime
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
                ai_seed, turn, file_mtime = rec
                last_mtime = file_mtime

                changed = (ai_seed != last_seed) or (turn != last_turn)
                if not changed:
                    time.sleep(POLL_INTERVAL_S)
                    continue

                wallclock_ms = int(time.time() * 1000)
                line = json.dumps({
                    "wallclock_ms": wallclock_ms,
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
                time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nstopped.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
