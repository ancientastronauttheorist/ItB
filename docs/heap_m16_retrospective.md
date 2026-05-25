# The Heap M16 Retrospective

Date: 2026-04-30

Mission: Detritus, The Heap (`Mission_AcidTank`)

Outcome: region secured at 2/7 grid. Defense Lab protected. ACID kill bonus missed at 3/4.

## What Happened

Turn 1 opened with four active threats:

- Firefly2 at D4 targeting E4.
- Scorpion1 at E3 targeting E4.
- Centipede1 at F3 targeting F4.
- Scarab1 at C2 targeting C7.

`cmd_solve` / `auto_turn` appeared to hang, so the harness used a direct Rust top-1 plan:

- TeleMech D7 -> D5, swap D4.
- Acid Tank G5 -> G2.
- IgniteMech G7 -> E8, fire E3.
- FlameMech C5 -> D2, fire C2.

The mission reached turn 2 at 4/7 grid.

## Root Causes

### Hidden Top-K Work In Default Solve

`cmd_solve(beam=0)` was documented as direct top-1, but the implementation used `itb_solver.solve_top_k(..., k=10)` whenever available and then replayed every candidate through the Python safety audit. That made the live path slower and harder to reason about than the emergency direct Rust call.

Fix: default `cmd_solve` now calls `itb_solver.solve` for true top-1 again. Beam modes still exist for wider search.

### Missing Pre-Solve Repro Payload

The first saved `m16_turn_01_board.json` was already post-action/enemy-phase, not the pristine player-turn input that hung. That made the stall impossible to reproduce exactly.

Fix: `cmd_solve` now writes `mNN_turn_NN_solve_input.json` before calling Rust. If a solve stalls again, this is the first artifact to inspect.

### Dirty Tactical Selection

The direct plan was tactically dirty. It saved the Defense Lab line but did not prove a no-grid-loss line. A later reconstruction found better candidates that projected one less grid loss, though no pristine original solve input exists for a perfect replay.

The interim enemy-phase read showing zero threatened buildings was misleading: bridge/UI state can be stale during animations. The reliable evidence is the pre-turn queued attacks and post-turn grid value.

## Follow-Ups

- Prefer true top-1 in the hot loop; use beam/top-k intentionally when we can afford it.
- Keep solve input artifacts for every solve attempt.
- Treat mid-animation `threatened_buildings: 0` as provisional when grid later drops.
- Investigate whether bridge building HP can stay stale while grid power updates, since turn-2 evidence showed grid loss without a matching saved building-HP delta.
