# Save-file timing experiment — when does `aiSeed` actually change?

## Background

The resist-probe logger in `src/loop/commands.py` (line 665, `_log_resist_probe`)
records `aiSeed` from `profile_Alpha/saveData.lua` once per `cmd_read` call at
the start of each player turn. In one recent mission the probe reported the
same `aiSeed = 560415071` on **both turn 2 and turn 3**, then a different seed
on turn 4. We need to know whether that repeat is real game-state (PRNG not
advancing between those turns) or a timing artifact (we read before the game
flushed the new seed to disk).

`scripts/watch_save_file.py` is the instrument that discriminates it.

## Running the experiment

1. Start a mission as normal — deploy, reach the first player turn.
2. In a **second terminal**, before you click End Turn, launch the watcher:

   ```bash
   cd /Users/aircow/Documents/code/claude/ItB
   python3 scripts/watch_save_file.py
   ```

   It polls `saveData.lua` every 250 ms and appends one line to
   `recordings/save_timing.jsonl` each time `aiSeed` OR `iCurrentTurn` changes
   in `region1` (the active region). It also prints `TURN ADVANCED` /
   `SEED CHANGED` to stderr in real time so you can watch events land against
   game-visible actions.

3. Play the mission normally — click End Turn, let the enemy animate, take the
   next player turn, etc. Each line in `save_timing.jsonl` is stamped with
   `wallclock_ms` (at detection) and `file_mtime` (when the game actually wrote
   the file). Correlate the two against what was visible on screen.

4. Ctrl-C to stop when the mission ends.

## What the output reveals

Each JSON line is `{"wallclock_ms", "ai_seed", "turn", "file_mtime"}`. The
timing of change-events against your End-Turn clicks discriminates four
scenarios:

### a) `aiSeed` changes at the End-Turn click (during enemy animation)

Expect a `SEED CHANGED` line within ~1–2 seconds of clicking End Turn, while
`turn` is still at the pre-End-Turn value. `file_mtime` is close to the click
wallclock. **Meaning:** the game commits the next-turn PRNG state as part of
writing out the end-of-enemy-phase save. Our probe — which reads at start of
the next player turn — would see the *new* seed, so a cross-turn repeat would
be real (rules out timing artifact).

### b) `aiSeed` changes at the start of the next player turn

Expect a `TURN ADVANCED` line (where both `turn` and `ai_seed` change in the
same record) a few seconds after the enemy animation ends, matching the UI
transition back to player control. **Meaning:** the seed is committed just
before the game hands control back. Our probe reads fresh-after-transition,
so again a cross-turn repeat is real.

### c) `aiSeed` never changes during the turn

No additional `save_timing.jsonl` line between the baseline at watcher start
and the mission's end (or only `iCurrentTurn` bumps, not `ai_seed`).
**Meaning:** the cross-turn-same-aiSeed observation is REAL. This is the H1
outcome — aiSeed is not a generic PRNG counter; it advances only on specific
event types (spawns, resist rolls where a resist actually fires, etc.), so
turns with no such event leave it untouched.

### d) `aiSeed` changes multiple times per turn

Multiple `SEED CHANGED` records inside a single turn boundary (or inside a
single enemy phase). **Meaning:** each RNG consumption event writes through
to disk — and our single end-of-enemy-phase snapshot is just the last value.
This would invalidate using aiSeed as a turn-start fingerprint and argue for
hooking the Lua `math.random` call directly.

## Mapping results to hypotheses

| Observation                                    | Supports   | Rules out           |
|------------------------------------------------|------------|---------------------|
| No change across turns 2→3, change at 3→4      | **H1**     | H2, H3              |
| Change at End-Turn click (scenario a)          | H2 or H1   | H3                  |
| Change at player-turn start (scenario b)       | H2 or H1   | H3                  |
| No change at all despite turn bumping          | **H1**     | H2, H3              |
| Multiple changes per turn (scenario d)         | refines H1 | H2 (single-snapshot)|
| Change AFTER our probe ran (mtime > probe ts)  | **H3**     | —                   |

The H3 check requires cross-referencing `save_timing.jsonl` file_mtimes
against the probe log's timestamps in `recordings/<run_id>/resist_probe.jsonl`
(or whichever file `_log_resist_probe` writes to). If the watcher shows a
seed-change event whose `file_mtime` is *after* the probe's read timestamp
for the same turn, then the probe raced the game's write — classic H3 — and
we should move the probe read to later in the turn or add an mtime-settled
retry.

## Caveats

- The script uses `mtime` short-circuiting to avoid re-reading on every 250 ms
  tick. If the game ever writes the same bytes back (unlikely but possible),
  no change event fires — but `mtime` will bump and we'll re-parse, so
  content-level changes are still caught.
- The brace-walker in `_extract_region1_block` assumes no `{` or `}` inside
  string literals inside the region1 block. This holds for current saveData
  format; if Fantasy Lua starts embedding literal braces in strings, the
  walker will return the wrong slice. No crash — the sub-regexes just fail
  to find `aiSeed` and the script waits for the next poll.
- A single retry (50 ms later) covers the mid-write race where `stat()` saw
  a new mtime but `read_text()` landed during a partial flush.
