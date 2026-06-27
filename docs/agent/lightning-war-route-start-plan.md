# Lightning War Atomic Preview-Board Route-Start Timer Plan

## Purpose

Lightning War is a timer achievement: finish the first two Corporate Islands
within 30 minutes of in-game time. From the automation's perspective, the
objective is to maximize successful actions that advance the two-island clear
while minimizing seconds spent on the live in-game timer.

The most expensive current waste is not combat solving. It is route-map and
mission-start uncertainty: ambiguous route-region matching, stale preview
state, fallback clicks, and early unpauses can spend live timer seconds without
actually entering the next mission.

The current speed patch is therefore an atomic, proof-gated route-start
transaction: prove the preview mission, then commit through the calibrated
little 8x8 preview board that highlights yellow on hover. Deeper pause/resume
optimizations should come after that transaction is reliable.

## Mission Timer Budget

Treat 3 minutes of in-game timer as the hard ceiling for each ordinary mission.
Lightning War needs two Corporate Islands within 30 minutes, but the automation
should not spend the whole average budget on any single battle. A mission that
approaches 3 minutes should be treated as a pace failure unless it is an
explicitly justified exception such as a boss or forced recovery state.

Earlier fast-walkthrough scripts reached roughly 1 minute 50 seconds per
mission, so the combat flow is known to be capable of beating this budget. The
main blocker was not action selection speed; it was unreliable UI clicking,
preview/start handling, and route-map transitions. The route-start plan should
therefore optimize for deterministic UI progress first, then use the 3-minute
mission ceiling to decide when a timeline should be abandoned or rerouted.

## Agent Use

Use agents liberally wherever and whenever they can reduce uncertainty, catch
edge cases, or review implementation details. Good uses include route identity
reviews, UI/click safety reviews, pause/resume audits, test-plan critiques,
regression triage, and post-attempt analysis.

Agents are especially useful before changing default Lightning War behavior or
before running another live attempt. Their findings should be folded back into
the active plan, tests, or focused docs instead of living only in chat.

## Implementation Roadmap

### 1. Route policy plumbing

Make routing mode explicit wherever the Lightning route stack asks for or
emits route commands.

- Add or thread route policy through route-map commands and emitted command
  strings.
- Lightning War paths should use `lightning_war`.
- Baseline and experiment paths should be able to use `lightning_baseline`.
- The conductor must not accidentally fall through to Lightning War routing
  when running a baseline flow.
- Route policy should be visible in logs and route-start candidates so later
  debugging can distinguish speed-mode choices from baseline choices.

This should be the first code change because route identity and route-start
proofs depend on knowing which policy produced the candidate.

### 2. Route identity and provenance

Attach a durable identity record to each visual route candidate before any
automatic start is allowed.

Each candidate should record at minimum:

- route policy
- assignment source
- assignment method
- assignment confidence/status
- visual region signature
- screenshot path or capture timestamp
- save source and freshness
- save region index
- mission slot/index
- mission id, when proven
- whether the route identity is exact, ambiguous, stale, or diagnostic only

Save-backed exact assignment is valid only when all of these are true:

- the island map is visibly clean enough for route matching
- the visual candidate count matches the save route option count
- save route indices and mission slots are unique
- duplicate mission ids are either absent or disambiguated by stronger proof
- the save data is fresh enough for the current map state
- no candidate in the selected path is unassigned

Bridge-preview mission ids should be diagnostic by default. They should not be
stamped onto multiple visible candidates, and they should not authorize
auto-start without exact route identity.

Raw coordinates and manual start coordinates may identify which preview to
open, but they must not create an expected mission id or bypass proof gates.

### 3. Atomic preview-board route start

Default Lightning War route start should use one narrow transaction:

1. Select the exact route candidate preview.
2. Capture or read fresh proof of the mission preview.
3. If an advisor or dialogue panel is present, dismiss it only after detection.
4. Re-prove that the same expected mission is still selected.
5. Click the calibrated small 8x8 preview board.
6. Verify transition into deployment, combat, or another expected post-start
   state.

The default Lightning War path should not deliberate over mission names once
fresh bridge/save/OCR proof identifies the preview. Dam, Satellite, Train,
Tides, Tanks, Volatile, and similar missions are routeable in speed mode when
the mission id is exact and post-start proof succeeds. The solver and safety
gates own combat risk; the route layer owns identity and transition proof.

Visible `Start Mission` text remains a useful explicit probe/fallback mode, but
it is no longer the speed default. If the preview board cannot be clicked, the
mission identity is stale/unknown/mismatched, or the click does not produce
deployment/combat proof, the command should stop paused with evidence instead
of spending more live timer. The output should include the screenshot,
candidate identity, expected mission, detected UI state, and the reason the
start was blocked.

### 4. Lazy resume as a later stage

Lazy resume is valuable, but it should not be the first implementation patch.
It is only safe after route identity and proof-gated preview-board route start
are stable.

When implemented, use a single helper for live boundaries. The helper should:

- resume only immediately before a live action
- require a fresh bridge heartbeat when bridge state is needed
- perform a fresh read after resume
- re-check the relevant preconditions before clicking or sending bridge commands
- return a blocked plan during dry runs rather than unpausing

Live boundaries include:

- route-start preview clicks
- advisor/dialogue-clearing clicks
- visible `Start Mission` clicks
- deployment bridge commands
- combat bridge commands
- End Turn clicks

Route planning, candidate ranking, save-route inspection, and dry-run output
should remain paused whenever possible.

Lazy resume and atomic start work should both be measured against the 3-minute
mission ceiling. If a mission consumes more than 3 minutes, post-attempt review
should separate combat decision time from UI transition time so the next patch
targets the actual timer leak.

## Edge Cases And Failure Modes

- Visual route order may not match save route order.
- Duplicate mission templates can make mission id alone unsafe.
- Save data, bridge preview data, and screenshots can all become stale.
- Computer vision can split, merge, or hallucinate route regions.
- R.S.T. compact preview/start layouts can differ from normal mission panels.
- Advisor dialogue can obscure the real preview and Start state.
- Yellow text detection can false-positive outside the Start button.
- Windows scaling, focus, and crop offsets can shift detected text locations.
- Manual coordinates may select a preview but must not bypass mission proof.
- Safety gates, failed clicks, map changes, and state transitions must
  invalidate route identity tokens.
- A stale heartbeat while visibly paused is expected; it becomes a failure only
  if it persists after resume or appears during a live bridge action.

## Test Requirements

Add focused tests for the route-start transaction before using it in live
Lightning War attempts.

Required coverage:

- exact save-backed visual route identity assignment
- duplicate mission ids staying tied to distinct visual regions
- route start accepting exact identity matches
- route start blocking when mission identity is stale, missing, or mismatched
- default Lightning War mode using calibrated preview-board commit
- advisor/dialogue dismissal followed by re-proof before Start
- baseline routing remaining baseline
- Lightning War routing using the atomic proof-gated preview-board path
- future lazy-resume behavior resuming only at live boundaries

Existing tests that expect board-click or region-repeat fallback behavior should
either move behind an explicit legacy mode or be rewritten to expect a block in
default Lightning War mode.

Likely test names:

- `test_lightning_build_save_island_map_mixed_slate_preserves_route_identity`
- `test_visual_route_candidates_keep_duplicate_mission_identity_by_visual_region`
- `test_lightning_route_start_visual_index_accepts_exact_route_identity_match`
- `test_lightning_route_start_commits_matching_preview_with_preview_board`
- `test_lightning_route_start_blocks_when_preview_identity_missing`
- `test_lightning_attempt_does_not_resume_before_paused_map_route_plan`
- `test_lightning_attempt_resumes_only_for_live_end_turn_click`

Likely legacy tests to rewrite or scope behind legacy mode:

- tests that expect text-click fallback as the default mode
- tests that expect board clicks before dialogue dismissal
- tests that repeat route-region clicks after preview identity fails
- tests that resume immediately before paused map routing

## Rollout Order

1. Add routing policy plumbing and logging without changing route-start behavior.
2. Add route identity/provenance to candidates and command output.
3. Require exact route identity for automatic Lightning War start.
4. Switch default Lightning War route start to proof-gated preview-board commit.
5. Keep visible-text, region-repeat, and compact-card clicks behind explicit
   fallback/probe modes.
6. Add lazy resume only after the atomic route-start path is stable.
7. Run another live Lightning War attempt and measure timer leakage on the route
   map before touching combat timing.
8. Enforce the 3-minute per-mission pace gate, using the historical 1:50
   fast-walkthrough mission time as the stretch target and evidence that the
   remaining bottleneck is UI reliability.

## Acceptance Criteria

The route-start patch is ready for live attempts when:

- a selected route candidate has exact, save-backed identity
- the selected preview is re-proven after any dialogue dismissal
- the calibrated preview board is the default mission-start click
- missing/stale/mismatched mission identity produces a paused block with evidence
- baseline flows do not inherit Lightning War routing choices
- no default path spends timer seconds on blind region or compact-card fallback
  clicks
- ordinary missions that exceed 3 minutes of in-game time are flagged as pace
  failures with enough telemetry to distinguish combat time from UI time

The later lazy-resume patch is ready when:

- dry runs do not unpause
- route planning does not unpause
- every live boundary performs resume, fresh heartbeat/read, and precondition
  re-check
- deployment and End Turn are re-audited after resume

## Commit Scope

This document started as a doc-only planning note, but it now tracks the active
preview-board implementation. When committing implementation work, stage it with
the related code/tests/docs that keep the route-start defaults coherent:

```bash
git add docs/agent/lightning-war-route-start-plan.md \
  docs/agent/lightning-war-runner.md \
  src/loop/commands.py \
  src/loop/lightning_runner.py \
  tests/test_lightning_runner.py \
  tests/test_lightning_war_tools.py
git commit -m "Speed up Lightning War route starts"
git push
```

Do not stage unrelated worktree changes while committing this plan.
