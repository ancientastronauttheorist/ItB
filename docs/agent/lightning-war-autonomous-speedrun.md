# Lightning War Autonomous Speedrun Design

Status: draft from 2026-06-05 brainstorm.

This document is the build plan for earning Blitzkrieg's Lightning War
autonomously by treating the run like a speedrun. The critical constraint is
that Python must own every live-clock state. Codex may think, diagnose, and
plan only when the bot has proven the game is paused or otherwise non-live.

## Target

Earn Lightning War with no human help:

- Squad: Blitzkrieg.
- Difficulty: Easy.
- Advanced Edition: OFF. The user has confirmed Lightning War can unlock with
  AE disabled; AE ON was mainly useful for hardening the solver.
- Objective: finish the first two Corporate Islands before the achievement
  timer reaches 30:00.
- Execution mode: repeated `/goal` attempts until the achievement unlocks.
- Human role: watch only. Do not require route, shop, deployment, restart,
  tactical, or code/development decisions during the autonomous run.

## Current Decisions

- Build a local Python speedrun conductor, not a Goal-mode loop that repeatedly
  hands live-clock control back to Codex.
- Codex consultation is allowed only from verified pause/non-live states.
- Solver budgets may be normal or long while paused. A 10 second solve is fine
  if the timer is stopped.
- During live-clock states, Python must continue deterministic play, pause as
  soon as possible, or hard-stop with evidence. It must not wait for Codex.
- Keep all screenshots from serious attempts. Raw data is never deduped away.
- Add an offline screenshot review script that identifies interesting frame
  deltas so Codex does not need to inspect hundreds of nearly identical frames.
- Compress old failed-attempt screenshots after summaries and review artifacts
  have been generated.
- Ignore Time Pods for this achievement.
- If grid is full, leave the shop/island immediately. Do not spend time buying
  optional cores, weapons, pilots, or reputation value.
- If the bot starts a different mission than intended, continue with the loaded
  mission unless the attempt is already failing a hard timer/grid gate. This is
  a speedrun, and recovering from a misclick is usually slower than playing.
- Aggressive restart is acceptable when the bot logs why the attempt is too
  slow and the next code/data fix is clear.
- First island target: under 15:00. Warn around 12:00 if HQ completion is not
  imminent. Hard restart at 15:00 with no grace extension.
- Second island pacing should also be gated. A good starting rule is to restart
  if island two is not started by roughly 16:30-17:00, then tune from data.
- Optional objectives do not matter. Optimize only for grid health, speed, and
  avoiding terminal failure.
- Grid/building damage is allowed within reason when grid remains above zero
  and the damage does not create compounding risk that costs more time later.
- Mech HP loss, mech death, and pilot KIA do not automatically restart the
  speedrun if the timeline survives and continuing is faster than restarting.
- No save rollback. Use only normal abandon/restart/new-run flows.
- The bot may restart Into the Breach and continue if the bridge/game becomes
  stale.
- Success proof can be either the visible popup or achievement sync. If the
  popup is seen, run sync afterward to confirm.

## Frame Dropping

Frame dropping does not mean "do not save similar screenshots." For this design
the raw recording should keep every successfully captured frame.

Frame dropping means a capture safety valve: if the screenshot sampler wakes up
for frame N but frame N-1 is still being captured or written, the sampler may
skip frame N and log a `dropped: true` row in `frames.jsonl` instead of falling
behind and interfering with play.

Default policy for Lightning War attempts:

- Target cadence: 2 seconds.
- Keep all successful frames.
- Do not perform similarity dedupe during capture.
- Drop only under backpressure, and record every drop.
- Prefer a missed frame over slowing live play.

## Route Mismatch

A route mismatch means the bot intended to start one mission, but the game
actually loaded another mission because the map, preview, dialogue, or click
state was ambiguous.

Policy:

- Before Start Mission: if the visible/bridge preview does not match the
  intended mission and the bot is still in a safe or nearly free state, reroute
  or restart if that is faster than committing.
- After Start Mission or deployment: if a different mission is loaded, play the
  loaded mission. Do not spend live clock undoing a misclick unless the attempt
  is already failing a hard pace/grid gate.
- Record screenshot evidence, intended mission, actual mission, route candidate
  list, game timer, and the click/control sequence that led to the mismatch.
- Mismatch telemetry should still drive future fixes. Continuing the loaded
  mission is a speed policy, not permission to ignore flaky route starts.

## Architecture

Add an in-process conductor, likely `src/loop/lightning_conductor.py`, and keep
the CLI thin:

```text
game_loop.py lightning_autonomous --achievement "Lightning War"
```

The conductor should call existing command helpers directly instead of shelling
out to `python3 game_loop.py` for each step. This keeps timing precise, avoids
stdout parsing overhead, and lets us attach structured spans around every
decision.

Proposed core classes:

- `AutonomousLightningConductor`: owns the run state machine.
- `LightningState`: setup, island select, map, preview, deployment, combat,
  reward, shop, pause, restart, success, blocked.
- `TelemetryRecorder`: append-only JSONL event log and summary generator.
- `ScreenshotRecorder`: background screenshot sampler with cached bounds.
- `PauseProof`: visible UI, timer source, timer stability, screenshot evidence.
- `RouteDecision`: selected mission, candidates, score, vetoes, expected cost.
- `ResetDecision`: restart reason, evidence, and next improvement hint.
- `CodexHandoff`: a packet written only after `safe_to_think == true`.

## State Machine

Python owns all live states:

```text
setup
  -> start_run
  -> island_select
  -> island_map
  -> mission_preview
  -> deployment
  -> combat
  -> reward_tail
  -> shop_or_leave
  -> second_island
  -> success
```

Allowed Codex/user thinking states:

- setup/title/main menu before the achievement clock starts.
- verified pause menu.
- verified non-live achievement/success/failure screen.
- hard-stop state after the conductor has paused or proven the timer is not
  advancing.

Forbidden Codex thinking states:

- island map while unpaused.
- mission preview/start confirmation while unpaused.
- deployment.
- player-turn combat unless pause has been verified first.
- enemy turn and animation waits.
- reward/shop/island transition screens unless pause/non-live is verified.
- any ambiguous UI where timer state is unknown.

If the bot cannot prove a safe thinking state, it must emit
`BLOCKED_UNPAUSED_CLOCK_TICKING` or continue deterministic automation.

## Pause-Safe Solver Policy

Combat should use a two-tier solve policy:

- Paused solve: once the pause guard proves the timer is stopped, allow normal
  or long solver time, such as 10 seconds.
- Live solve: keep only bounded tactical work that is known to be fast, or get
  to pause first.

Preferred combat rhythm:

```text
pause proof
  -> solve with generous budget
  -> resume
  -> execute bridge actions with verification
  -> click End Turn
  -> wait through enemy turn
  -> pause as soon as player turn is available
```

The solver can spend time while paused; execution and enemy waits are the live
segments to minimize.

## Telemetry Artifacts

Serious attempts should write under `recordings/<run_id>/telemetry/`:

```text
recordings/<run_id>/telemetry/
  events.jsonl
  frames.jsonl
  screenshots/
    000001_123456789_live.png
    000002_123458789_live.png
  summary.md
  interesting_frames.md
  frame_deltas.jsonl
  contact_sheet.png
```

`run_notes/` remains useful for small smoke tests. `recordings/<run_id>/` should
be the source of truth for serious Lightning War attempts.

Do not record video for the primary Lightning War pipeline. Screenshots plus
JSONL are easier to index, diff, cite, compress, and feed into Codex as selected
frames/contact sheets. The review pipeline should focus on frame deltas,
contact sheets, and structured timing summaries.

## Event Schema

Every event row should include:

```json
{
  "schema_version": 1,
  "event_id": "evt_...",
  "run_id": "...",
  "event_type": "command_span",
  "wall_time": "2026-06-05T00:00:00-05:00",
  "wall_unix": 1780000000.0,
  "monotonic_ns": 123456789,
  "span_id": "span_...",
  "parent_span_id": null
}
```

High-value event types:

- `clock_sample`: authoritative game timer, timer source, read latency.
- `guard_sample`: safe-to-think result, pause proof, visible UI, screenshot ref.
- `command_span`: command/helper name, wall duration, game timer delta, status.
- `combat_turn`: turn number, solve wall time, execute wall time, enemy wait,
  end-turn detection, actions completed.
- `route_decision`: candidates, selected mission, vetoes, route score, expected
  timer cost.
- `screenshot_frame`: frame path, capture latency, nearest game timer, phase.
- `speed_loss_decision`: accepted/blocked grid, building, objective, pod, or
  mech loss.
- `restart_decision`: full-run restart reason and evidence refs.
- `codex_handoff`: emitted only from verified safe states.
- `success`: popup/sync evidence and final timer.

## Screenshot Review Script

Add an offline script, likely `scripts/lightning_frame_delta_report.py`, that
processes a completed run recording:

```text
python3 scripts/lightning_frame_delta_report.py recordings/<run_id>
```

The script should keep raw screenshots intact and generate derived review
artifacts:

- `frame_deltas.jsonl`: pairwise frame difference scores.
- `interesting_frames.md`: grouped timestamps with image links and reasons.
- `contact_sheet.png`: compact visual index of selected frames.
- `segments.csv`: rough live segment boundaries and durations.

Suggested algorithm:

1. Read `frames.jsonl`.
2. Load each frame, downscale to a small grayscale image.
3. Mask the timer area so the clock ticking by itself does not create false
   positives.
4. Optionally mask stable borders or overlays once their locations are known.
5. Compute a cheap perceptual hash or absolute pixel delta between frame N-1
   and frame N.
6. Flag frames whose delta is above threshold.
7. Group adjacent flagged frames into events.
8. Pick first, middle, and last frame from each event group.
9. Attach nearest telemetry span and game timer.
10. Write Markdown plus a contact sheet.

This gives Codex a shortlist like "mission preview changed at 04:12, deployment
began at 04:28, enemy turn ended at 06:01, reward panel stuck for 18 seconds"
instead of hundreds of images.

## Timing Questions The Data Must Answer

Each failed attempt should make these answerable:

- How much in-game time was spent before first island selection?
- How long did each mission take start-to-start?
- How much time was route map, preview/dialogue, deployment, combat execution,
  enemy animations, reward panels, shop/leave, and island transition?
- Did any Codex/human thinking happen while the clock was live?
- How much time did pause proof cost?
- How much time did screenshots cost?
- How much time did bridge ACKs and verification cost?
- How often did route previews mismatch intended missions?
- Which mission types were slow in practice, not just on paper?
- Which UI waits were conservative and tunable?
- Which restarts happened, and what fix would prevent the same restart?

## Routing Policy

The conductor should route for speed, not reputation:

- Prefer missions with low turn limits, short enemy wait cycles, simple
  deployment, few blocking panels, and no fragile allied-state complications.
- Prefer Train, fast battle missions, Tides/Tidal when reliable, and other
  proven short missions.
- Deprioritize Satellite, Dam, Bad Repairs, fragile ally objectives, Detritus
  barrels/vats/disposal, Mines/pods, and any mission with known desync or
  research friction when faster alternatives exist.
- Pods and optional reputation are expendable.
- Do not restart solely because the first island slate looks poor before mission
  one. Try to handle any mission; use telemetry to learn which islands/slates
  are consistently faster.
- If no fast route is visible and timer budget is already poor, restart because
  the pace gate is failing, not because the slate is aesthetically bad.

Because the user has no island preference, island choice should be empirical:
record island, slate, route choices, first-island finish time, and restart
reason. Archive/R.S.T. are current favorites, but the conductor should follow
measured speed.

## Advanced Edition Off

The first dedicated autonomous strategy should run with AE OFF. The user has
confirmed the achievement can unlock with AE OFF, and AE ON was mainly used to
stress-test solver coverage during broader achievement hunting.

Required code work:

- Teach setup verification to explicitly check desired AE state.
- Add an `--advanced-content off|on|any` option to the autonomous runner, with
  `off` as the Lightning War default.
- Ensure `lightning_preflight` reports whether AE state matches the run plan.
- Record AE state in the run manifest and summary.

AE OFF is attractive because it may reduce mission/enemy/equipment complexity.
The risk is that current code/docs assume AE ON in several places, so setup
verification must be explicit before Start.

## Restart Policy

Restart the full run when:

- Wrong squad, difficulty, achievement target, timer state, or AE state.
- First island is not complete by 15:00.
- Island two has not started by the current second-island gate, initially
  16:30-17:00 pending telemetry.
- Timer reaches 30:00.
- A slow loaded mission makes the active pace gates impossible.
- Persistent research, desync, post-enemy block, threat-audit block, or
  unresolved safety gate appears.
- Grid collapse is likely.
- Codex consultation would be required while the timer is live.
- A game/bridge stale state cannot be recovered faster by restarting the game.

Do not automatically restart only because:

- A route mismatch loaded a playable mission.
- Optional objectives failed.
- A pod was lost.
- A building or grid damage line is faster and grid remains above zero.
- A mech takes damage, dies, or causes pilot KIA, provided the timeline survives
  and continuing remains the faster route.

Every restart must log:

- game timer and wall time.
- current island/mission/phase/UI.
- screenshot refs.
- route and command span history.
- reason category.
- proposed next fix or route-policy update.

## Goal-Mode Development Strategy

The desired final operating mode is `/goal`: repeated autonomous attempts until
Lightning War unlocks. The hard question is whether the same goal run should
also make code/docs fixes between attempts.

### Option A: Attempt-Only Goal

The goal runner plays attempts, restarts, records telemetry, and stops or parks
only when a verified safe handoff is needed.

Pros:

- Clean separation between live play and development.
- Lower risk of editing code while game/session state is half-active.
- Easier to audit: every attempt used a known code version.
- No surprise test/build latency inside an achievement attempt.

Cons:

- If a repeated bottleneck is obvious, the bot cannot fix it immediately.
- Requires a separate development thread between goal runs.
- More human/Codex orchestration around "review, patch, try again."

### Option B: Self-Improving Goal

The goal runner can pause safely, inspect telemetry, patch code/docs, run tests,
and resume attempts with the improved code.

Pros:

- Best fit for long unattended iteration.
- Repeated failures can become fixes without waiting for a new session.
- Pairs naturally with the screenshot-delta report and `summary.md`.
- Useful once the runner is mature and most failures are narrow/tactical.

Cons:

- More moving parts while the game is open.
- Harder to prove which code version produced each attempt.
- Test/build cycles can take wall time and may leave the game parked for a long
  time.
- Must never edit/reload live-control code while the timer is running.
- Needs strict commit/version metadata so telemetry remains trustworthy.

### Option C: Hybrid Goal

Run attempts autonomously. If an attempt fails, park in a verified safe state,
generate telemetry summaries, and classify the failure:

- `retry_without_code_change`: routing/slate/randomness looked acceptable.
- `parameter_update`: safe config threshold or route score update can be made
  without touching core code.
- `code_fix_needed`: stop live attempts, patch/test, record new version, then
  resume repeated attempts.

Pros:

- Keeps live attempts fast and auditable.
- Still lets the system improve when telemetry shows a real repeated loss.
- Reduces the risk of making large code changes during an active timeline.
- Works well with `/goal` because the goal can continue after verified
  paused-state development.

Cons:

- Requires a failure classifier and versioned run manifests.
- Some fixes still require the goal to pause for a long development cycle.
- Slightly less autonomous than a fully self-improving loop.

Chosen policy: use Option C as the "Hybrid Theory" operating mode. The bot
should retry on ordinary failed attempts, make small parameter/data updates only
from verified safe states, and stop live play for real code changes. After a
code change, it should run focused tests, record the new code version in
telemetry, then continue attempts.

## Optimization Backlog

High-value improvements:

- Replace the subprocess conductor with an in-process autonomous conductor.
- Add the telemetry recorder and screenshot sampler first, before changing many
  behaviors.
- Add offline screenshot delta analysis.
- Make Lightning War achievement target explicit at run creation.
- Add AE OFF setup/preflight support.
- Make full-run restart one command from any verified safe state.
- Improve route scoring and empirical island/slate preference from telemetry.
- Tighten first-island and second-island pace gates.
- Tune click settle times with telemetry evidence.
- Benchmark `pause_between_actions` and make it adaptive.
- Reduce redundant bridge reads where ACK state dumps are already reliable.
- Keep bridge fast mode for combat without paying ACK timeout on map/reward
  screens.
- Record enemy-turn wait duration separately from solver/execution duration.
- Make reward/shop tails deterministic: clear panels, take grid if needed,
  leave immediately if grid full.
- Generate `summary.md` automatically after every run.

## Implementation Phases

Phase 1: documentation and telemetry skeleton.

- Add this design doc.
- Add `TelemetryRecorder` with JSONL events and `summary.md`.
- Add `ScreenshotRecorder` with cached bounds, 2 second cadence, and backpressure
  logging.
- Add tests for artifact paths and event schemas.

Phase 2: screenshot review tooling.

- Add `scripts/lightning_frame_delta_report.py`.
- Mask timer region.
- Emit `interesting_frames.md`, `frame_deltas.jsonl`, `segments.csv`, and a
  contact sheet.
- Test on existing smoke screenshots where possible.

Phase 3: in-process conductor.

- Add `src/loop/lightning_conductor.py`.
- Reuse existing `cmd_lightning_segment`, `cmd_lightning_attempt`,
  `cmd_lightning_loop`, route start validation, and pause guard helpers.
- Keep `scripts/lightning_war_conductor.py` as a compatibility shim if useful.
- Add `game_loop.py lightning_autonomous`.

Phase 4: AE OFF and setup automation.

- Add explicit AE desired-state verification.
- Support `--advanced-content off`.
- Start from verified setup without human clicks.
- Record setup proof in telemetry.

Phase 5: speedrun policy.

- Implement first-island 12:00 warning and 15:00 restart gate.
- Implement the second-island start gate.
- Continue through loaded route mismatches unless pace/grid gates fail.
- Implement restart for pace failure, grid collapse, stale unrecoverable state,
  and timer failure.
- Implement shop leave-if-grid-full.

Phase 6: attempt, review, tune.

- Run a telemetry-first attempt.
- Use `summary.md` and `interesting_frames.md` to identify the largest timer
  losses.
- Patch the single largest loss class.
- Repeat until the first island is consistently below 15:00 and second island
  completion is plausible below 30:00.

## Success Criteria

The bot is ready for serious repeated attempts when:

- It can start a Lightning War run from verified setup without human input.
- It records every live segment and screenshot frame.
- It never consults Codex unless `safe_to_think` is proven.
- It continues loaded route mismatches when playable, and restarts full runs
  automatically on pace, timer, setup, grid, or unrecoverable-state failure.
- It produces a readable `summary.md` after every attempt.
- It can explain where the last failed attempt lost timer.
- It can complete island one under 15:00 in repeated practice runs.

The final target is a fully autonomous command that can run until Lightning War
unlocks, with Codex used only as a paused-state builder/debugger during
development and no human live intervention.
