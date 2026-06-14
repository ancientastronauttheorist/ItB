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

The workflow should behave like a timing lab, not a broad autonomous player.
Each pass isolates one UI boundary, captures 2 Hz visual evidence, updates the
executable timing profile when the evidence improves it, then restarts from the
main menu and repeats from the top.

## Current Calibration Target

The first autonomous lab target is:

```text
main menu -> final difficulty Start click -> Archive island click -> red mission map
```

The live timer starts at the exact click that presses the lower Start button on
the Difficulty Setup modal. The first milestone succeeds only when at least one
red mission region is detected on the Archive mission map. Merely reaching the
island selection screen or a generic island map is not enough.

Hardcoded island order for Lightning War calibration:

1. Archive, Inc.
2. Pinnacle Robotics

The mission target itself should not require strategy thinking during timing
calibration: click a valid red mission, not the "best" red mission. The red
mission detector must still be robust enough to avoid boundary clicks between
two adjacent red regions and must return proof for the chosen target.

Expected island structure: each island has five red missions to clear. The first
four ordinary missions should be UI-equivalent for mission selection. The fifth
mission is the HQ mission and has a different map/UI behavior: it can spend many
frames becoming the only selectable red mission. Put extra care into the red
detector and route-map branch evidence because this detector will be reused
through all ten required island missions.

## Operating Pattern

Each discovery cycle starts from the main menu and replays from the top.

Do not treat an intermediate UI state as a restart anchor. We cannot reliably
restart directly to arbitrary points such as new-run setup, island selection,
mission preview, or deployment. Those states can be observed during a pass, but
the next proof pass must reset to the main menu and replay every already proven
slice before extending the route.

The cycle is:

1. Reset to the main menu known start state.
2. Start high-cadence screenshots at 0.5 seconds (2 Hz).
3. Execute only the next intended UI/action slice.
4. Stop at the first new uncertain UI boundary, or continue capturing until
   timeout if the run is already stuck and more evidence is useful.
5. Review screenshots and structured logs to identify:
   - first visible transition frame
   - first frame where the next button/control appears
   - first frame where the control is safely clickable
   - any animation, dialogue, focus, or stale-bridge delay
6. Encode the newly proven click/wait/check pattern.
7. Restart to the main menu known start state.
8. Replay the proven route plus the new slice.
9. Repeat until the whole two-island Lightning War route is covered.

Do not try to discover multiple uncertain UI boundaries in one live attempt.
The loop is intentionally repetitive: prove one boundary, restart to the main
menu, replay from the top, extend the script by one boundary, and test again.

The user should stay in the loop during discovery. When a timing choice, branch
classification, or failed click needs judgment, stop with a "next timing patch"
report rather than silently papering over the uncertainty.

## Mode Toggle

Use two complementary modes.

**Observe/build mode** is the slow mode. Use it when the next UI boundary is
unknown, when a click target has not been proven, or when a recent failure needs
diagnosis. In this mode, capture high-cadence evidence, stop at the first new
uncertain boundary, think while paused or reset, and patch only the newly proven
wait/click/check pattern.

**Fast-attempt mode** is the pressure-test mode. Use it when the route is
proven up to the current frontier. Start from the main menu, replay the known
route at speed, and continue until one of these happens:

- the achievement is earned
- the run reaches the next unproven UI boundary
- the route fails, blocks, desyncs, or spends live timer without progress
- a hard safety, research, diagnosis, or bridge gate appears

After a fast-attempt stop, switch back to observe/build mode for the postmortem.
If failures are not immediate, still force a think/postmortem pass at least
every other fast attempt so timing drift and small wastes do not accumulate
unnoticed.

## Screenshot Cadence

Use 0.5 second screenshots during UI timing discovery.

This cadence is higher than normal autonomous attempt telemetry because the
purpose is not merely postmortem evidence. The purpose is frame-level timing:
which screen appeared when, how long animations took, and when a visible
control became clickable.

Capture policy:

- keep every successful frame while it remains inside the rolling buffer
- never dedupe during capture
- record frame timestamps and wall-clock intervals
- prefer a dropped frame over slowing live automation
- keep screenshots grouped by attempt and route slice
- keep high-cadence screenshot directories gitignored
- retain raw screenshots for only the latest three attempts total
- keep contact sheets and manifests longer; they are much smaller than raw
  screenshots and are valuable for human memory
- keep generated screenshots, contact sheets, and manifests gitignored unless a
  human explicitly promotes a small artifact
- implement raw screenshot retention with labeled attempt directories when
  available, plus a hard frame-count cap as a fallback for unlabeled samples
- for autonomous recorder runs, the current default cap should cover roughly
  three minutes of rolling evidence at 0.5 second cadence

The frame stream should make it possible to reconstruct the UI transition
without relying on memory or chat notes.

Screenshots are the primary evidence source in both calibration and fast
attempts, as long as they do not materially slow the run. When screenshot
capture threatens live speed, prefer dropped frames over delaying clicks.

## Timing Profile

Use a two-file timing profile:

- `data/lightning_war_timing_profile.json` is the executable truth consumed by
  the lab script and fast route scripts.
- `docs/agent/lightning-war-timing-profile.md` is the human lab notebook that
  explains evidence, branches, failed attempts, and why each timing exists.

This split keeps automation simple while preserving the reasoning trail. JSON
is easy to validate, diff, and update automatically. Markdown is easier to read
when deciding whether a timing is trustworthy or whether a branch needs more
work.

Profile entries should be named in plain boundary language, for example:

- `difficulty_start_to_island_select`
- `archive_island_click_to_red_map`
- `red_map_to_mission_preview`
- `hq_red_map_to_mission_preview`

When a timing is proven across repeated runs, record the most common successful
timestamp rather than the fastest outlier. This leans slightly toward
robustness while still optimizing the in-game timer.

If a new result is clearly better, the lab loop may auto-edit the JSON timing
profile. After every approved or clearly improved profile update, commit and
push the profile/code/doc changes. Generated screenshots, contact sheets, and
manifests remain ignored and uncommitted.

## Branches

Lightning War timing is a flowchart, not a single straight line. The lab loop
must learn every path that can still lead to the achievement.

Branch examples:

- default island intro
- extra CEO/advisor dialogue
- time pod appeared
- reward, shop, or pod UI appeared
- ordinary mission red-map state
- fifth-mission HQ red-map state
- post-island leave/confirmation flow

Branch-specific timings belong in branch-specific profile sections, for
example:

```text
archive_intro.default
archive_intro.extra_dialogue
archive_intro.time_pod
archive_red_map.ordinary
archive_red_map.hq
```

When a new branch appears, capture until timeout or until the branch is clearly
classified, then stop for a next timing patch report. Do not force the default
route assumptions onto a branch that is visually different.

## Clickability Standard

For timing purposes, "clickable" means the first frame where the control is
visible and an attempted click can be proven to advance the screen. If a button
is visible at 5.5 seconds but only a 6.0 second click works, the 6.0 second
timestamp wins.

For unfamiliar controls, use hover proof when needed to determine that the
visual element is actually a button. Once a control has been proven, hot runs
may skip hover proof and rely on visual detection unless detector confidence
drops or a branch changes the layout.

Use visual detectors where they can run fast enough. They are preferred over raw
coordinates because the loop should eventually work on macOS and Windows and
across different resolutions, screen sizes, and aspect ratios. It is acceptable
for the first implementation of a detector to work only on the current layout,
but the timing profile and evidence should not pretend it is globally proven
until it has been hardened.

Each variable click target should record its provenance:

- source screenshot frame
- boundary name and branch label
- bounding box
- click point
- area
- detector confidence or heuristic
- whether the click advanced the screen
- contact sheet path and frame timestamp

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

For the first lab implementation, target only the opening slice through red
mission map detection. Later implementations can extend the same loop to
mission preview, deployment, combat turns, rewards, shop/leave flow, second
island selection, and the HQ mission states.

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
- memory-reader in-game timer value, when available and validated against the
  visible screenshot timer
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
- the result has enough screenshot evidence for the user to verify the timing

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

Mission budget target:

- hard ceiling: 3 minutes per mission
- preferred target: 2 minutes per mission

These mission budgets include UI overhead required to reach and clear the two
islands for Lightning War. Boundary-specific time limits will vary by branch,
but each boundary should be treated as a candidate for shaving timer seconds
once its correctness is proven.

## Automation Rules

- Start from the main menu for discovery. A parked or intermediate state may be
  used only to inspect evidence or recover safely, not as the canonical start of
  the next timing proof.
- Unless the user explicitly asks to continue from the current screen/state,
  every timing-lab proof run starts from the main menu and replays the proven
  route from the top. Current-combat or already-visible-panel probes may collect
  useful side evidence, but they do not satisfy a timing proof request by
  themselves.
- Build the autonomous timing lab as a new small script rather than adding more
  complexity to the fast walkthrough script.
- Keep the user in the loop during discovery, especially when choosing the next
  slice to extend.
- Standing permission is granted to use agents liberally wherever and whenever
  they help: planning, edge-case review, detector design, timing analysis,
  branch classification, postmortems, and code review. Do not parallelize live
  game-touching commands; keep `game_loop.py` and UI-control commands serialized.
- Use screenshots for novel UI and timing boundaries.
- Use bridge reads for combat state once combat is loaded.
- Lightning War timing-lab fast attempts may skip a post-action
  `FUZZY_INVESTIGATE_BLOCKED` safety stop only when `auto_turn` has already
  completed the full opening squad action count and returned a held End Turn
  plan. This is a speedrun-specific edge-case policy: record the skipped block
  signature in the timing report, click End Turn, and keep measuring the route.
  Do not generalize this exception to ordinary achievement play, diagnosis
  runs, or combat states without a held End Turn plan.
- Region Secured Continue is a proven Windows control at window-relative
  `(1647, 985)`. The timing lab should hover it for proof and then click it by
  default; use `--no-region-secured-click-continue` only for hover-only audits.
- Bridge-ready is the default speed signal after Deploy Confirm and End Turn.
  The timing lab should use `--post-confirm-extra-ready-frames 0`,
  `--post-end-turn-extra-ready-frames 0`, `--no-pause-after-opening-player-turn`,
  and `--no-pause-after-combat-player-turn` by default so the next solve starts
  from the bridge transition instead of waiting for screenshot/pause evidence.
  Re-enable the pause flags only for slower audit/proof runs.
- The from-top speed-route expectation is the short sequence
  `enemy(opening) -> us1 -> enemy1 -> us2 -> enemy2 -> us3 -> enemy3->done`.
  The timing lab hard-records this with `--speed-expected-player-turns 3` and
  tightens Region Secured visible polling on expected turn 3. If a longer
  route appears, the lab must report the mismatch and continue the dynamic loop
  rather than stopping early.
- Use the live in-game timer memory reader only after a numeric candidate has
  been validated against pause-menu `Timeline Playtime` across a
  pause -> unpause -> re-pause cycle. For the current Windows process/session
  and PID 2100, `0x00000000122e5dbc` with kind `f32_seconds` is the validated
  live numeric timer. It survived two live tracking cycles and a 2 Hz
  screenshot filename smoke; use it with
  `--memory-live-timer-address 0x00000000122e5dbc --memory-live-timer-kind f32_seconds`.
  Rediscover it after game restart, PID change, modloader reload, or platform
  change. In the same process, `0x00000000138a5900` is only a pause-menu
  render/cache address for
  `Timeline Playtime`: it matched visible paused values at `0h 1m 04s`,
  `0h 1m 27s`, `0h 1m 48s`, `0h 2m 14s`, `0h 2m 47s`, and later `0h 21m 27s`,
  but stayed stale while the live top-right timer advanced. Use that address as
  a ground-truth oracle after re-pausing, not as the live screenshot frame
  clock. Treat unanchored context summaries, `visible_timer_string` aggregates,
  other string hits, and unvalidated numeric candidates as diagnostic only.
- Never run two live `game_loop.py` commands at the same time.
- Stop and park when a UI state is ambiguous.
- On failure, try to reach the pause menu first before longer thinking.
- Do not spend timer while Codex thinks; pause or reset first.
- Prefer named controls and visible text proof over raw coordinates.
- Raw coordinates may be used only after screenshot evidence shows they are
  stable for the current window layout.

The lab script should produce a next timing patch report after each attempt.
Reports should include the result, branch label, chosen timing, evidence
summary, and the most relevant frames/contact sheet path so the user can judge
the next step quickly.

## Restart Discipline

The restart is part of the method, not a setback.

After each newly proven UI boundary:

1. Save the evidence.
2. Update the script or route notes.
3. Restart to the main menu known start state.
4. Replay all proven slices.
5. Extend by exactly one new uncertain slice.

This keeps timing comparable across attempts and prevents late-run state drift
from being mistaken for a reliable route.

In practice, "restart" means return to the title/main menu, then execute the
full proven sequence again. If the live game is parked at setup, island map,
deployment, combat, or a reward screen, first abandon or otherwise recover to
the main menu before starting the next measurement pass.

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
