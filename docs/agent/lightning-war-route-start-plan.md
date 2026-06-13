# Lightning War Atomic Route-Start Timer Plan

## Purpose

Lightning War is a timer achievement: finish the first two Corporate Islands
within 30 minutes of in-game time. From the automation's perspective, the
objective is to maximize successful actions that advance the two-island clear
while minimizing seconds spent on the live in-game timer.

The most expensive current waste is not combat solving. It is route-map and
mission-start uncertainty: ambiguous route-region matching, stale preview
state, fallback clicks, and early unpauses can spend live timer seconds without
actually entering the next mission.

The first speed patch should therefore be an atomic, proof-gated route-start
transaction. Deeper pause/resume optimizations should come after that
transaction is reliable.

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

### 3. Atomic Start-text-only route start

Default Lightning War route start should use one narrow transaction:

1. Select the exact route candidate preview.
2. Capture or read fresh proof of the mission preview.
3. If an advisor or dialogue panel is present, dismiss it only after detection.
4. Re-prove that the same expected mission is still selected.
5. Click visible `Start Mission` text only.
6. Verify transition into deployment, combat, or another expected post-start
   state.

The default Lightning War path should not use board-click, region-repeat, or
compact-side-card fallback clicks after a missing Start text detection. Those
fallbacks are useful only behind an explicit legacy/manual mode.

If Start text cannot be proven, the command should stop paused with evidence
instead of spending more live timer. The output should include the screenshot,
candidate identity, expected mission, detected UI state, and the reason the
start was blocked.

### 4. Lazy resume as a later stage

Lazy resume is valuable, but it should not be the first implementation patch.
It is only safe after route identity and Start-text-only route start are stable.

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
- route start blocking when Start text is missing
- default Lightning War mode refusing board/region/compact fallback clicks
- advisor/dialogue dismissal followed by re-proof before Start
- baseline routing remaining baseline
- Lightning War routing using the atomic Start-text-only path
- future lazy-resume behavior resuming only at live boundaries

Existing tests that expect board-click or region-repeat fallback behavior should
either move behind an explicit legacy mode or be rewritten to expect a block in
default Lightning War mode.

Likely test names:

- `test_lightning_build_save_island_map_mixed_slate_preserves_route_identity`
- `test_visual_route_candidates_keep_duplicate_mission_identity_by_visual_region`
- `test_lightning_route_start_visual_index_accepts_exact_route_identity_match`
- `test_lightning_route_start_commits_matching_preview_with_visible_start_only`
- `test_lightning_route_start_blocks_when_start_text_missing_without_board_fallback`
- `test_lightning_attempt_does_not_resume_before_paused_map_route_plan`
- `test_lightning_attempt_resumes_only_for_live_end_turn_click`

Likely legacy tests to rewrite or scope behind legacy mode:

- tests that expect `dialogue-region-repeat-preview-board` as the default mode
- tests that expect board clicks before dialogue dismissal
- tests that repeat route-region clicks after Start text is missing
- tests that resume immediately before paused map routing

## Rollout Order

1. Add routing policy plumbing and logging without changing route-start behavior.
2. Add route identity/provenance to candidates and command output.
3. Require exact route identity for automatic Lightning War start.
4. Switch default Lightning War route start to Start-text-only.
5. Move old fallback click modes behind explicit legacy/manual flags.
6. Add lazy resume only after the atomic route-start path is stable.
7. Run another live Lightning War attempt and measure timer leakage on the route
   map before touching combat timing.

## Acceptance Criteria

The route-start patch is ready for live attempts when:

- a selected route candidate has exact, save-backed identity
- the selected preview is re-proven after any dialogue dismissal
- `Start Mission` text is the only default mission-start click
- missing Start text produces a paused block with evidence
- baseline flows do not inherit Lightning War routing choices
- no default path spends timer seconds on blind board, region, or compact-card
  fallback clicks

The later lazy-resume patch is ready when:

- dry runs do not unpause
- route planning does not unpause
- every live boundary performs resume, fresh heartbeat/read, and precondition
  re-check
- deployment and End Turn are re-audited after resume

## Commit Scope

This document is intended as a doc-only planning commit. It should be staged and
committed by itself:

```bash
git add docs/agent/lightning-war-route-start-plan.md
git commit -m "Document Lightning route-start timer plan"
git push
```

Do not stage unrelated worktree changes while committing this plan.
