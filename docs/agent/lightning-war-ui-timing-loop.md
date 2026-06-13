# Lightning War UI Timing Discovery Loop

## Purpose

This loop is the empirical workflow for rebuilding the fast Lightning War
walkthrough one UI boundary at a time.

The achievement goal remains the same: earn Lightning War by maximizing the
number of successful actions that move the run toward a two-island clear while
minimizing the number of live in-game timer seconds spent doing it.

The key hypothesis is that combat speed is already good enough. Earlier fast
walkthrough versions reached roughly 1 minute 50 seconds per mission, and the
current planning budget treats 3 minutes as the hard ceiling for an ordinary
mission. The bottleneck to solve first is UI reliability: knowing exactly when
screens change, when buttons become clickable, and which click pattern is safe
to automate without wasting live timer.

## Operating Pattern

Each discovery cycle starts from a known fresh state, preferably the main menu
or new-run setup before the Lightning War timer starts.

The cycle is:

1. Reset to the known start state.
2. Start high-cadence screenshots at 0.5 seconds.
3. Execute only the next intended UI/action slice.
4. Stop at the first new uncertain UI boundary.
5. Review screenshots and structured logs to identify:
   - first visible transition frame
   - first frame where the next button/control appears
   - first frame where the control is safely clickable
   - any animation, dialogue, focus, or stale-bridge delay
6. Encode the newly proven click/wait/check pattern.
7. Restart from the known start state.
8. Replay the proven route plus the new slice.
9. Repeat until the whole two-island Lightning War route is covered.

Do not try to discover multiple uncertain UI boundaries in one live attempt.
The loop is intentionally repetitive: prove one boundary, restart, extend the
script by one boundary, and test again.

## Screenshot Cadence

Use 0.5 second screenshots during UI timing discovery.

This cadence is higher than normal autonomous attempt telemetry because the
purpose is not merely postmortem evidence. The purpose is frame-level timing:
which screen appeared when, how long animations took, and when a visible
control became clickable.

Capture policy:

- keep every successful frame
- never dedupe during capture
- record frame timestamps and wall-clock intervals
- prefer a dropped frame over slowing live automation
- keep screenshots grouped by attempt and route slice

The frame stream should make it possible to reconstruct the UI transition
without relying on memory or chat notes.

## Slice Boundaries

Good slices are small enough that one failure teaches exactly one thing.

Examples:

- main menu to new-run setup
- setup verification to final Start click
- final Start click to first island selection
- island click to clean route map
- route candidate click to mission preview
- advisor dialogue detection and dismissal
- mission preview to Start Mission clickable
- Start Mission click to deployment screen
- deployment confirm to combat player turn
- End Turn click to next player turn
- final mission clear to island reward/shop/leave screen

If a slice crosses combat and UI, split it unless the combat section is already
fully proven. UI timing discovery should isolate UI uncertainty, not hide it
inside tactical execution.

## Metrics

Every cycle should record:

- run id or attempt id
- route slice name
- starting screen
- intended ending boundary
- screenshot cadence
- first transition frame timestamp
- first clickable frame timestamp
- click coordinates or named control
- live timer before and after the slice, when available
- whether the slice advanced achievement progress
- whether any timer seconds were spent without progress
- next hypothesis or patch needed

Timer analysis should separate:

- combat decision/solve time
- combat execution time
- enemy animation wait time
- route-map UI time
- mission preview/start UI time
- deployment UI time
- reward/shop/leave UI time

This separation matters because the historical fast walkthrough proves that
mission execution can be fast enough; most remaining waste is expected to come
from UI transitions and click uncertainty.

## Pass And Fail Rules

A slice passes when:

- it starts from the intended known state
- it reaches the intended next boundary
- screenshot evidence proves the UI transition timing
- the clicked control is reproducible by named control, text proof, or stable
  window-relative coordinate
- any live timer spent is explained by actual progress

A slice fails when:

- it reaches a different UI state than intended
- screenshots cannot identify when the control became clickable
- a click lands during animation or stale state
- the game spends live timer without achievement progress
- the script needs manual human correction to continue
- the resulting mission pace would violate the 3-minute ordinary mission
  ceiling without a clear recovery reason

Failures should not be papered over by adding blind waits. Prefer a stronger
state proof, a better click target, or a smaller slice.

## Automation Rules

- Start from main menu or new-run setup for discovery unless testing a later
  slice requires a saved parked state.
- Keep the user in the loop during discovery, especially when choosing the next
  slice to extend.
- Use screenshots for novel UI and timing boundaries.
- Use bridge reads for combat state once combat is loaded.
- Never run two live `game_loop.py` commands at the same time.
- Stop and park when a UI state is ambiguous.
- Do not spend timer while Codex thinks; pause or reset first.
- Prefer named controls and visible text proof over raw coordinates.
- Raw coordinates may be used only after screenshot evidence shows they are
  stable for the current window layout.

## Restart Discipline

The restart is part of the method, not a setback.

After each newly proven UI boundary:

1. Save the evidence.
2. Update the script or route notes.
3. Restart from the known start state.
4. Replay all proven slices.
5. Extend by exactly one new uncertain slice.

This keeps timing comparable across attempts and prevents late-run state drift
from being mistaken for a reliable route.

## Relationship To Other Lightning Plans

This document complements:

- `docs/agent/lightning-war-route-start-plan.md`
- `docs/agent/lightning-war-autonomous-speedrun.md`
- `docs/agent/lightning-war-progress-economy.md`

The route-start plan defines the desired safe transaction. This timing loop is
how to discover the exact UI transition timings and clickability windows needed
to make that transaction fast.

The output of this loop should feed back into code, tests, and focused docs.
Do not leave timing discoveries only in chat.
