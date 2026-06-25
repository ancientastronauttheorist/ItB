# Lightning War Runner

Status: repo implementation present as of 2026-06-06; live two-island
validation is still pending.

Validation state:

- Unit and helper coverage proves the baseline/speed CLI wiring, setup proof
  flow, route-gate retry budget, grid-first shop blocks, OCR terminal guards,
  stale-heartbeat/desync/reload stop signs, and speed telemetry buckets.
- The requested live proof is not complete until
  `lightning_autonomous --mode baseline --target-islands 2` reaches
  `target_islands_completed` from the main menu or a verified setup state while
  preserving the final OCR-backed success proof.
- Live attempts through `20260607_210306_865` proved setup, route start,
  deployment, combat, End Turn handling, reward classification, perfect-grid
  reward handling, and route rerolls across multiple fresh timelines. The
  current live validation blocker is tactical reliability: `Mission_Dam` and
  `Mission_Disposal` produced real safety blocks and are baseline-vetoed, while
  `Mission_Tides` exposed a false `THREAT_AUDIT_BLOCKED` that is covered by
  lower-UID Scorpion friendly fire before the building hit. The requested
  two-island live proof is still pending.

Use the autonomous runner for a conservative two-island Lightning War baseline:

```bash
python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 20
```

Baseline assumptions:

- Squad is Blitzkrieg, difficulty is Easy, and Advanced Content is OFF unless
  the command overrides those setup values.
- The runner may start from the title screen, the new-game setup screen, or an
  already active Lightning War session.
- Title-screen entry requires CV evidence for the calibrated title buttons
  before clicking New Game. Setup entry may click the new-run screen's
  top-right Start button only to open the difficulty modal; the final
  `setup_modal_start` click that begins the run is delegated to
  `lightning_start_run` and requires `verify_setup` to pass first.
  `verify_setup` fails closed when it cannot prove the screenshot came from the
  Into the Breach window.
- First-island selection uses one calibrated island click. Do not confirm by
  clicking the same island coordinate again; once the corp map opens, that
  coordinate can select a mission region.
- After the verified setup Start click, the start helper takes one classifier
  snapshot before the first-island click. Explicit system/privacy prompt
  evidence blocks as `external_system_prompt_visible`; unknown classifier
  evidence is recorded but does not by itself stop the just-started timeline.
  Once the first-island click is sent, the helper first records a pending
  `lightning_first_island_clicked:<island>` session tag. It promotes that tag
  to `session.current_island` only after pause/corp-map evidence is verified or
  when it is deliberately handing off to `lightning_segment`, so a later resume
  cannot blindly click the same island coordinate again.
- If a system prompt blocked the run after setup Start but before first-island
  selection, rerunning the autonomous runner may recover the half-started run
  only when the session has no current island, no current mission, mission
  index 0, no completed islands, and CV still sees the conservative
  `island_map_or_unknown` selection shape. It then uses the same calibrated
  first-island click, intro clear, and pause verification path.
- After Start, and before continuing an existing session, the runner verifies
  the active session says Blitzkrieg/Easy/Lightning War, the active
  save/profile Advanced Content flags match the configured target, and the save
  loadout contains Blitzkrieg's expected mech and weapon IDs:
  `ElectricMech`, `WallMech`, `RockartMech`, `Prime_Lightning`,
  `Brute_Grapple`, and `Ranged_Rockthrow`. Upgraded weapon suffixes such as
  `Prime_Lightning_A` satisfy the base weapon proof.
- Combat remains delegated to the existing Lua bridge plus Rust solver through
  `lightning_segment`; the runner does not make manual combat decisions.

Baseline policy:

- `time_limit` defaults to 10 seconds. The runner pauses on rest/UI screens, but
  combat bursts run unpaused so the Lua bridge heartbeat keeps ticking while
  `auto_turn` solves and executes.
- `lightning_speed_loss_policy` is off.
- Dirty plans and objective-loss override flags are off.
- Safe panel auto-clear is disabled inside `lightning_segment` so the runner
  can classify visible panels itself.
- If `lightning_segment` stops on a panel-ready state, the runner immediately
  reclassifies and clears known safe panels before consuming another segment
  loop. `island_complete_leave` still uses the grid-first shop path below.
- The runner requests OCR when it classifies terminal-prone panels, handoffs,
  and success proofs. Manual investigations can collect the same evidence with
  `python3 game_loop.py lightning_ui classify --include-ocr`. The lower-level
  `lightning_ui handle_screen` and `clear_tail_pause` helpers also stop instead
  of clicking when an otherwise clearable panel carries explicit terminal/OCR
  evidence.
- Safe-panel clearing is disabled when the classifier payload carries explicit
  terminal evidence, including KIA/timeline-lost flags or OCR/text fields such
  as `visible_text`, `ocr_text`, `objective_texts`, or raw nested
  `ocr.texts`/`ocr.lines` containing failed objective text. KIA wording
  includes `Killed in Action`, `Pilot Lost`,
  `Mech Lost`, `KIA`, and `K.I.A.`. Plain objective-row OCR such as
  `Protect the Train Failed`,
  split objective/OCR rows such as `Protect the Train` followed by `FAILED`,
  structured objective rows such as `{status: "failed"}` or `{failed: true}`,
  string-valued terminal flags such as
  `{terminal_outcome: "Killed in Action"}`,
  and failure headings such as `FAILED MISSION` also block, while generic helper
  errors like `screenshot failed` do not.
  Bridge-refined `terminal_panel_false_positive` payloads and OCR-clean
  `kia_panel` classifier crops are not terminal proof by themselves; they remain
  non-clearable unless another safe panel/control is visible, but they do not
  block as `terminal_outcome_visible` without explicit text/flag evidence.
  Bare unaudited `kia_panel` screens still block pause-guard and runner terminal
  checks until inspected.
- The pause guard applies the same OCR-backed terminal-evidence audit before
  clicking Pause on reward/continue panels, so it must block instead of hiding
  visible KIA/timeline-lost/failed-objective evidence behind the pause menu.
- If startup pause guard saw a safe reward/continuation/shop panel before
  entering pause, the runner may resume once, clear that hidden panel, and
  re-pause before combat. This startup shortcut deliberately excludes mission
  previews so route validation still owns Start Mission clicks.
- A visible mission-preview dialogue may be dismissed with its text box, but a
  visible `Start Mission` preview board is not treated as a generic safe panel.
  The runner blocks with `mission_preview_requires_route_validation` instead of
  clicking the board unless the route-start path has already proved the mission
  identity.
- On `island_complete_leave`, the runner reads save grid power, clicks Spend
  Reputation, buys Grid Power until max, verifies each purchase, then leaves.
  After closing the shop it reclassifies the screen and clicks Leave only after
  `island_complete_leave` is visible again. After confirming Leave, it
  classifies the handoff screen and accepts only routeable continuation states
  such as island map, bottom-continue, or pause before continuing to another
  island. An ambiguous `island_map_or_unknown` handoff blocks before the
  requested island target is complete because it could hide a failed transition
  or unexpected panel. If grid state, a purchase, the shop-to-leave transition,
  or the post-leave handoff cannot be verified, it blocks with evidence.
- Route auto-start is on by default, using the existing route validation inside
  the Lightning segment helpers. Baseline mode uses
  `routing=lightning_baseline` and keeps route vetoes enforced; speed mode uses
  `routing=lightning_war`.
- `--first-island` is the preferred first attempt, not a single-island prison.
  On safe pre-combat route-gate rerolls that abandon to verified setup, the
  runner rotates fresh first-island starts through
  Archive -> R.S.T. -> Pinnacle -> Detritus, beginning with the configured
  preference. This spends the reroll budget exploring different corporate
  mission slates instead of repeatedly sampling one bad Archive opening.
- When a visible map only yields unlabeled red-region candidates, the
  autonomous runner passes a `route_probe_offset` based on the fresh-attempt
  number, mission index, and completed-island count. That rotates which visual
  region is preview-probed after safe setup rerolls, preventing repeated
  first-region-only failures. The offset never demotes a candidate with a
  verified mission id; save/bridge mission proof still outranks blind probes.
- Baseline routing treats train, Dam, Disposal, Satellite, Tanks, Bad Repairs,
  fragile/counter objectives, and similar avoid-listed missions as no-surprise
  reliability vetoes. `Mission_Tides`, `Mission_Mines`, `Mission_Cataclysm`,
  and `Mission_Artillery` are allowed through the normal Rust solver and safety
  gates for baseline evidence, even though speed mode may rank them
  differently.
- The autonomous runner uses strict route matching for baseline and speed mode:
  if a Start Mission click loads a different live mission than the expected
  route target, route-start writes mismatch evidence, tries deployment-screen
  recovery when available, and the segment stops before deployment. If retry
  budget remains, the runner abandons to verified setup and rerolls the attempt;
  it does not silently continue a different corporate mission.
- Route auto-start prefers a verified expected mission id. When the visible map
  only yields unlabeled red regions, the segment may click one region to open
  its live bridge preview, but it clicks Start Mission only if that preview
  exposes a mission id. In speed mode that mission must also pass the
  Lightning War speed veto policy.
  If the Lua bridge reports a mission preview while CV still sees multiple red
  map regions, the visible map planner treats that bridge preview as ambiguous
  and falls back to save/CV route candidates, even when save-to-visual
  assignment is only unlabeled. This prevents one stale preview mission from
  being stamped onto every visible red region.
  The same save/CV fallback applies when a live `bridge` island-map
  recommendation produces multiple red regions but none of the candidate
  commands has a mission assignment. A compact top-route hint may guard a route
  command only for a single unassigned visible region; with multiple unassigned
  regions, exact mission guards require per-region save-backed assignment.
  Save/profile `region_id` values are not visual click indices; if CV does not
  provide a detected red-region candidate, auto-start blocks rather than
  guessing a coordinate. If a live preview names the wrong mission before Start,
  the segment rejects that visible candidate without clicking Start Mission.
  If a preview probe itself blocks as vetoed, unverified, mismatched, or
  unassigned before Start Mission, the segment records that route candidate as
  rejected and first tries another distinct candidate from the same island route
  recommendation/route-start candidate list. It never reuses a rejected source
  id, never treats OCR as Start authority, and still blocks before Start when
  candidate evidence is ambiguous. Retrying from an already-open preview is not
  a safe same-island scouting path: the guard blocks as
  `route_preview_existing_mission_preview_before_region_click` before clicking
  another region, and the outer runner may abandon/restart only while the stop
  is still preview-only. If a preview probe reaches turn-zero deployment before
  the explicit Start click, the runner accepts it only when the actual mission
  is present and not vetoed by the active baseline/speed route policy; vetoed or
  missing mission ids still write route-mismatch evidence and recover instead of
  deploying.
  If the bridge is absent but visible preview OCR matches known mission-specific
  text such as `Defend the Satellite Launches` or `Defend the Tanks`, the
  segment records `visible_preview_ocr` and uses that mission id for route
  policy. Speed-mode routing treats OCR as veto-only evidence and still blocks
  safe-looking OCR previews before Start. Baseline routing may use OCR as Start
  authority only when the recognized mission id is not vetoed by the
  conservative baseline route policy and the normal visible Start Mission /
  post-start mission verification path still passes. A direct route-start with
  `--expected-mission-id` may use matching baseline OCR when the bridge preview
  stays silent, and baseline may also accept unknown/silent OCR when the
  selected visual region already has a save-backed, non-vetoed expected mission
  id; contradictory OCR still blocks, and the Start commit must still produce
  fresh deployment or combat proof before deployment automation may run.
  If the bridge preview already has a safe mission id but multiple red regions
  are visible, the segment may still validate that exact expected mission id
  through `lightning_route_start` before Start. If there is no expected mission
  id and the selected preview came from a multi-region, unassigned map, speed
  mode still blocks as `route_preview_unassigned_multi_region_before_start`
  after preview evidence and before the irreversible Start Mission click.
  Baseline mode may proceed only when the verified bridge preview is
  baseline-safe and CV finds a visible `Start Mission` button; if that button is
  absent, it blocks as
  `route_preview_unassigned_multi_region_start_button_missing_before_start`
  instead of using the board-click fallback. The segment treats preview blocks
  as rejected candidates first; the outer runner abandons to verified setup and
  rerolls only after same-island candidates are exhausted or the stop is no
  longer preview-only.
  Avoid-listed missions such as Satellite, Dam, Disposal, Bad Repairs,
  fragile/counter objectives, and kill-limit/kill-count bonuses are blocked
  before deployment in baseline when the conservative route policy marks them
  unsafe. Speed mode keeps the narrower Lightning War speed veto policy and
  continues to require bridge-backed proof or explicit safe OCR-free routing
  before fast starts.
- If old bridge JSON reports phase-unknown deployment while CV sees
  `island_map` or `island_map_or_unknown`, the runner treats the bridge data as
  stale and asks the save/CV route planner for verified red-region candidates
  instead of deploying.
- If the pause guard sees a `title_screen` or setup false positive while a fresh
  bridge heartbeat says an active combat phase is live, bridge evidence wins and
  the guard clicks Pause instead of treating the screen as a safe rest state.
- If a route-auto-start refusal happens before any route start or combat, or
  after a preview-only route start that blocked before Start Mission, the
  runner may use `lightning_abandon_to_setup` and start a fresh setup, up to
  `--max-attempts`. It does not abandon a run for generic combat safety gates,
  desyncs, research, or uncertain post-combat screens.
- If the initial preflight proves the visible/effective Lightning War timer is
  already over 30 minutes, and the active metadata still proves a
  Blitzkrieg/Easy/Lightning War session, the runner may also abandon to setup
  and start a fresh verified attempt within `--max-attempts`. Other preflight
  failures still block for inspection.
- Each segment appends a compact `segment_result` telemetry row with mode,
  status, reason, wall time, game timer, step count, speed-policy flag, and
  session progress.
- Final success proof emits `completion_screen_proof` telemetry rows for both
  the initial OCR-backed classifier pass and any pause-peek pass, recording the
  proof source, visible UI name, status, block reason, and compact evidence.
  These proof rows are best effort: if a proof telemetry write fails, the runner
  keeps the strict proof decision and carries the write failure in
  `telemetry_event_errors`.
- Before returning `target_islands_completed`, the runner performs one final
  OCR-backed screen proof. It accepts only known completion-proof screens such
  as a reward panel, island-complete/leave screen, or verified island map. If
  the pause menu hides the proof screen, it performs a `lightning_peek` with
  OCR, returns to pause, and audits the revealed evidence before accepting
  success. If the session says the target island count is complete but the
  visible or peeked screen carries KIA, timeline-lost, failed-objective,
  system-prompt, title/setup, or ambiguous `island_map_or_unknown` evidence,
  the runner blocks instead of declaring success from stale session state.
- Achievement-sync success also performs a classify-only proof before returning
  success. Initial already-unlocked sync may still be on title/setup, but any
  terminal, KIA, failed-objective, system-prompt, or classification-failure
  evidence blocks the success shortcut.

Speed mode is the same state machine with the Lightning War speed policy and a
shorter default combat budget:

```bash
python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3
```

Speed mode preserves the normal stop signs. It does not enable dirty-plan
consent, timeline collapse, mech-loss acceptance, stale-board continuation, or
blind unknown-screen clicks.

The older `lightning_start_run` helper is also baseline-safe by default:
Easy difficulty, Advanced Content OFF, no `lightning_speed_loss_policy`, and
no objective-loss consent unless those flags are passed explicitly.

If a run was started and then blocked by a system prompt before first-island
selection, use the guarded first-island resume helper after the prompt is gone:

```bash
python3 game_loop.py lightning_select_first_island --first-island archive --advanced-content off
```

It refuses to click unless the active session and save/profile state prove a
Blitzkrieg/Easy/Lightning War attempt with the expected Advanced Content state
and Blitzkrieg mech/weapon loadout. It also blocks if that session already
records an island, mission, mission index, completed island, or a pending
first-island click that cannot be promoted from a verified pause/corp-map
state.

Speed-mode optimizations:

- `time_limit` defaults to 2 seconds.
- Repeated per-segment preflight is skipped after the first clean segment unless
  the runner is in baseline mode; hard gates from the segment still block.
- The speed runner blocks with `first_island_pace_gate` when no island is
  complete after `first_island_gate_seconds`. It blocks with
  `second_island_start_pace_gate` when exactly one island is complete, no next
  mission has been recorded, and the timer has passed
  `second_island_start_gate_seconds`. If the second island already has a
  current mission, the runner continues instead of treating the start gate as a
  mid-mission failure.
- `lightning_speed_loss_policy` is passed to `lightning_segment`, preserving the
  narrow documented Lightning War loss exception.
- `segment_result` telemetry rows retain compact step, route, combat-loop, and
  turn-timing summaries without storing bulky quiet stdout in the event.
- Speed mode also emits `speed_phase_timing` rows with the segment status,
  phase label, current island/mission, completed-island count, game timer, wall
  seconds, and compact combat-turn timing totals. Phase labels are
  `between_missions`, `route`, `mission`, `reward_shop`, and
  `target_complete`. Use these rows to tune route, shop, and solver budgets
  after the baseline is live-reliable. `segment_result` and
  `speed_phase_timing` writes are independent best-effort rows, so a failure in
  one does not suppress the other.

Primary recovery results:

- `preflight_failed` - clear setup, target, timer, or other non-stop-sign
  preflight issues before rerunning. An initial over-budget timer can be
  restarted automatically only when the active session metadata already proves
  Blitzkrieg/Easy/Lightning War and a retry budget remains.
- `research_required`, `post_enemy_blocked`, `threat_audit_blocked`,
  `safety_blocked`, or `investigation_required` - a stop-sign token appeared in
  preflight or nested segment evidence. Inspect `stop_evidence.path` or
  `preflight.stop_evidence.path` when present, follow the named protocol, and
  do not continue combat or End Turn from the old evidence.
  Stop-sign evidence can come from structured `status`/`reason` fields or from
  string payloads such as helper stdout, warnings, or messages; string-carried
  evidence includes a compact `text` excerpt. Overlapping tokens such as
  `INVESTIGATE_POST_ENEMY` are routed to the more specific protocol. Human
  prose variants such as `post-enemy`, `threat audit`, `safety blocked`,
  `requires research`, `objective failed`, and `timeline lost` are normalized
  to the corresponding stop-sign family. If a generic parent status wraps more
  specific nested evidence, `stop_evidence.path` points at the nested gate.
  For same-family wrappers such as `SAFETY_BLOCKED`, nested evidence wins only
  when it carries more specific detail than the parent label.
- `pause_guard_initial_exception` - the initial pause/visible-state guard
  raised before the runner could prove whether the screen was title, setup,
  pause, or live combat. Inspect the traceback/window evidence before starting,
  resuming, or clicking any timeline control.
- `achievement_sync_exception` - the Steam/local achievement sync helper raised
  either before startup or after a safe segment. Inspect the traceback/output
  evidence before trusting achievement state or continuing.
- `preflight_exception` - the read-only Lightning preflight helper raised before
  a combat burst. Inspect the traceback/output evidence and rerun preflight
  before continuing.
- `lightning_segment_exception` - the start-to-next-decision helper raised
  during routing, deployment, combat, or post-mission handling. Stop before more
  UI or combat commands; recover visible/bridge state, then resume only from a
  fresh read plus solve or fresh setup proof.
- `session_load_exception` - the runner could not read active session metadata
  at startup, setup proof, pace/progress checks, after a segment, or after an
  island-leave handoff. Inspect the `stage`, traceback, and any nested
  segment/shop evidence; do not trust stale island progress until session reads
  succeed again. During a route-gate retry this appears as nested
  `restart_session_load_exception` under `route_gate_restart_failed`.
- `telemetry_start_exception` - telemetry could not be created before the
  runner took live actions. Fix the recorder/path issue, or explicitly accept a
  weaker evidence source before rerunning.
- `screenshot_start_exception` - the background screenshot recorder failed
  before the runner touched the live game. The runner stops with telemetry and a
  skipped frame-delta summary; rerun with screenshots disabled only after
  deciding the remaining evidence is sufficient.
- `telemetry_rehome_exception` - the runner started a new Lightning timeline
  but could not move recording output into the new run directory. The run may
  continue using the existing telemetry directory; inspect the event before
  reconciling screenshots or manifests later.
- `runner_exception` - a remaining uncategorized helper raised unexpectedly.
  Inspect the `command_span` exception event plus the `traceback` payload; the
  runner has stopped instead of continuing from uncertain state.
- `segment_failed` - `lightning_segment` returned a tokenless top-level
  `ERROR`/`BLOCKED` failure. Inspect `segment_failure` plus the compact segment
  evidence and visible state before rerunning; the runner stops immediately
  instead of repeating the same failed helper result. If a helper returned a
  malformed non-dict value, `segment_failure` and the compact evidence use
  `command_returned_non_dict` with `value_type` / `value_repr`.
- `max_segments_reached` - the bounded runner loop ran out of segment budget.
  Inspect `islands_completed`; if the final progress read failed, the result
  keeps nested `session_load` evidence instead of pretending the island count is
  known.
- `title_new_game_exception` / `classify_after_title_new_game_exception` - the
  title-screen New Game helper or the immediate post-click classifier raised.
  Preserve the traceback/window evidence, regain a visible title or setup
  screen, and rerun setup proof before starting a Lightning War timeline.
- `setup_start_exception` - the helper that opens Start from the setup screen
  raised before visual setup proof. Preserve the traceback/window evidence,
  regain a visible title or setup screen, and rerun setup proof before starting
  a Lightning War timeline.
- `setup_not_verified` / `setup_verification_exception` /
  `setup_click_exception` - the visual setup verifier failed, raised, emitted a
  bad click plan, or a setup adjustment click raised before the Difficulty Setup
  overlay could be reverified. Preserve the screenshot/error/traceback evidence
  and rerun `verify_setup` before starting a timeline.
- `lightning_start_run_exception` - setup proof passed, but the final
  start-run helper raised. Inspect the traceback/window evidence and rerun
  visible setup proof before accepting or starting the timeline.
- `first_island_selection_failed` - the post-setup first-island resume helper
  could not prove an unselected first-island state, could not click the
  calibrated island control, or could not verify the pause path. Preserve the
  visible/session evidence before any more island-coordinate clicks.
- `first_island_selection_screen_unverified` / `first_island_click_failed` -
  the guarded first-island helper either did not see the conservative
  first-island selection shape or could not click the calibrated island control.
  Preserve the classifier/click evidence and recover to verified setup or
  pending-island confirmation before another island click.
- `first_island_session_unverified` - the standalone first-island recovery
  helper did not confirm an active Blitzkrieg/Easy/Lightning War session.
  Correct the session/setup state before any first-island click.
- `first_island_save_state_unverified` - the standalone first-island recovery
  helper found missing or mismatched save/profile proof: save difficulty,
  Advanced Content state, or Blitzkrieg mech/weapon loadout. Correct or restart
  the attempt before any first-island click.
- `first_island_selection_pending_unverified` - a prior first-island coordinate
  click is recorded in session tags, but the visible screen does not prove it
  reached the corp map. Do not click the island again; recover to verified
  pause/corp-map evidence before promoting the pending marker.
  The autonomous runner preserves this and other first-island session/pause
  persistence failures as top-level reasons rather than wrapping them as a
  generic first-island failure.
- `setup_state_unverified` - the session/save proof did not confirm
  Blitzkrieg, Easy, Lightning War targeting, Advanced Content target, or
  expected Blitzkrieg loadout. If `save_state.reason` is
  `setup_save_state_reader_exception`, inspect the traceback before trusting
  active session metadata or starting a timeline.
- `first_island_pace_gate` / `second_island_start_pace_gate` - speed mode is
  too far behind its configured island timing thresholds; inspect the
  `pace_gate` telemetry row and restart from a safe state before continuing a
  serious Lightning War attempt.
- `failed_objective_detected`, `kia_detected`, or
  `timeline_collapse_detected` - nested segment/combat evidence reports a
  terminal Lightning War failure. The runner stops without an extra pause or
  abandon click; inspect `stop_evidence.path` plus screenshot/log evidence
  before any recovery action.
- `bridge_snapshot_unavailable` - nested combat/segment evidence says the
  bridge snapshot is unavailable. Recover the bridge/window state, then resume
  only from a fresh read plus solve.
- `repeated_progress_state` - a lower-level segment made the same non-progress
  transition repeatedly. This usually means stale bridge state, a misclassified
  visible map/deployment screen, or a helper retry loop; inspect fresh
  read/classify evidence before rerunning.
- `mission_preview_requires_route_validation` - a visible Start Mission preview
  board lacks verified route proof. Do not click Start Mission; regain a
  verified island-map route candidate or bridge-preview mission id first.
- `deployment_bridge_state_uncertain` - deployment state is ambiguous. Preserve
  visible/bridge evidence and regain a verified deployment or map state before
  Confirm Deployment, Start Mission, or combat commands. A stale bridge
  heartbeat can never prove that route Start reached deployment, even if the
  stale snapshot still says `in_active_mission=true`.
- `visible_island_map_without_bridge` - CV sees a routeable map but live bridge
  proof is absent. Use fresh classify/save route evidence before choosing or
  starting a mission.
- `visible_island_map_with_stale_deployment_bridge` - CV sees the island map
  while bridge state still looks like deployment. Treat bridge state as stale
  and regain fresh classify plus bridge/save route proof.
- `ambiguous_route_start_region` - visual route-region detection could not
  match a verified mission candidate. Inspect the map screenshot and rerun route
  detection from a fresh paused/classified map.
- `hard_gate` with `stop_token` - inspect `stop_evidence.path` plus the nested
  segment/preflight evidence for the exact matched helper payload. Named
  stop-sign tokens are promoted to the recovery results above.
- Returned segment hard-stop evidence is promoted before the post-segment
  session/progress read. This includes stale heartbeat, terminal evidence,
  solver/combat timeout, desync, research/safety/post-enemy stop signs, and
  route-gate/remaining stop tokens or tokenless segment helper failures, so
  stale or crashing session metadata cannot hide the actual live stop sign.
- `terminal_outcome_visible` - a visible panel or returned segment payload
  carried explicit KIA, killed-in-action, mech-loss, timeline-lost, or
  failed-objective evidence. Inspect
  the nested `terminal_evidence` path and screenshot before clearing any UI,
  syncing achievements, or continuing combat. Returned segment terminal evidence
  is promoted before the post-segment session/progress read, so a stale or
  crashing session reader cannot hide the terminal screen evidence.
- `terminal_outcome_visible_before_success` - session progress reached the
  requested island count, but the final classify-only success proof found
  terminal or failed-objective evidence. Treat the visible screen as
  authoritative until inspected.
- `completion_screen_unverified` / `completion_pause_peek_failed` /
  `completion_pause_peek_exception` - session progress reached the requested
  island count, but the final visible or pause-peek proof was ambiguous,
  failed, raised, or did not show a known completion screen. The compact
  `completion_block.peek` evidence keeps the screenshot path, notes path, OCR
  flag, live-burst timing, and pause/capture verification when available;
  exception blocks keep `exception_type`, `error`, and traceback. Regain a
  visible reward, island-complete, or verified island-map screen before
  accepting success.
- `post_leave_handoff_ambiguous_before_target` - after leaving an island, the
  next screen classified only as `island_map_or_unknown` while more islands
  remain. Inspect the screenshot/visible state and regain a verified next-island
  map, bottom-continue, or pause state before routing.
- `screen_classification_failed` / `screen_classification_exception` /
  `visible_panel_handle_exception` /
  `mission_preview_dialogue_clear_exception` /
  `mission_preview_dialogue_post_classify_exception` /
  `completion_screen_classification_failed` /
  `completion_screen_classification_exception` - the CV classifier could not
  prove the current screen, or a panel clear/classify helper raised before the
  next safe state was verified. Preserve the screenshot/error/traceback
  evidence and do not click through or accept stale session progress as success.
- `stale_bridge_heartbeat` - a combat burst saw `Bridge heartbeat stale` /
  `Lua stopped ticking`, or nested segment evidence carried `STALE_HEARTBEAT`
  / `STALE_BRIDGE`. The runner stops with nested evidence; recover the bridge
  and resume only from a fresh read plus solve, never from the old partial-turn
  solution.
- `combat_desync` - a nested combat burst reported `DESYNC`. The runner stops
  without route restart or pause clicks, carries `stop_evidence.path` for the
  exact nested payload, and requires recovery from a fresh read plus solve
  before any more combat commands or End Turn clicks.
- `solver_or_combat_timeout` - a nested combat burst reported a solver timeout,
  empty solver result, or player-turn wait timeout. The runner stops with the
  nested timeout evidence. Recover the visible/bridge state and resume only from
  a fresh read plus solve; recovered deployment ACK timeout notes such as
  `ACK_TIMEOUT_BUT_PLACED` are not treated as this block.
- `reload_or_main_menu_visible` - nested segment CV evidence says the title
  screen or new-game setup screen appeared during an active Lightning War run.
  Treat this as a reload/crash/main-menu state; inspect the visible screen and
  session state before starting or continuing any timeline. Do not trust stale
  session progress; resume an existing combat timeline only after a fresh read
  plus solve, or restart only after fresh setup verification.
- `external_system_prompt_visible` - a macOS privacy/system prompt is covering
  the game window. The classifier returns `system_privacy_prompt` with no
  recommended control; runner results keep the prompt kind and screenshot path
  as evidence. Nested segment prompts carry `external_prompt_evidence.path`.
  The nested evidence may come from `system_privacy_prompt`,
  `requires_user_authorization`, a matched `external_prompt`, or prompt prose.
  The detector has a strict crop path and a relaxed prompt path for the smaller
  translucent macOS screen/audio prompt; both require distinctive privacy icon,
  text, button, and card evidence before overriding in-game panel classifiers.
  Route-gate restart attempts preserve this as the top-level stop reason instead
  of wrapping it as a generic retry failure. The runner will not click `Allow`
  or dismiss the prompt automatically. Ask the user for explicit authorization
  or dismissal, then resume from the current visible game screen.
- `route_auto_start_not_allowed` - the route scorer, visual assignment, or live
  preview probe did not prove a safe mission handoff, and either the retry
  budget is exhausted or the refusal happened after a non-preview
  route-start/combat signal. Do not click Start Mission from an unverified or
  vetoed preview. Preview-only route gates before Start Mission, including
  `route_preview_auto_start_vetoed_before_start`,
  `route_preview_mission_unverified_before_start`, and
  `route_preview_unassigned_multi_region_before_start`, are restartable only
  while attempt budget remains and no combat signal is present.
- The default `lightning_autonomous --max-attempts` budget is 20 because Archive
  can repeatedly roll only unsafe visible starts, such as all candidates
  OCR-vetoed as `Mission_Tanks`. These rerolls are still limited to
  preview-only gates before any Start Mission click or combat signal, and they
  primarily apply to speed-mode vetoes or baseline cases where mission identity
  could not be proven.
- `route_gate_restart_failed` - a route gate was restartable, but abandoning
  back to setup, restarting, or re-verifying the new setup failed. Inspect the
  nested `restart` evidence before any more UI clicks. If the nested reason is
  `abandon_to_setup_exception`, preserve the traceback/window evidence and
  regain a verified setup or pause-safe state before retrying.
  `attempt_restart` telemetry rows are best effort; write failures are reported
  in `telemetry_event_errors` and do not cancel a safe retry or replace the
  nested restart failure.
- `post_segment_panel_blocked` - `lightning_segment` stopped because UI was
  ready, but the immediate classifier pass found a terminal or unexpected
  screen instead of a safe panel, or the pause-menu resume helper raised before
  revealing the expected panel. Inspect the nested `panel` and `segment`
  evidence before any more clicks; a nested
  `resume_paused_segment_panel_exception` or `ensure_pause_exception` means the
  pause/panel state must be visually re-established. If `ensure_pause_exception`
  is nested under another block, preserve the original stop evidence too; the
  pause failure does not make the earlier gate safe to ignore.
- `visible_panel_blocked` with
  `unexpected_menu_or_setup_visible_mid_run` - the title screen or new-game
  setup screen reappeared after a Lightning War session was already active.
  Inspect the screenshot/session state before restarting; the runner will not
  click New Game or Start from that state.
- `visible_panel_handling_failed` - inspect the visible panel before any more UI
  clicks. Nested shop/leave reasons ending in `_exception`, such as
  `shop_grid_power_click_exception`, `shop_exit_classification_exception`,
  `leave_confirm_exception`, or `post_leave_classification_exception`, preserve
  `exception_evidence`, grid state, and the ordered shop `steps`; do not click
  Leave or route again until that evidence proves the handoff is safe.
- `repeated_no_progress_state` - the runner saw the same session/UI/segment
  signature repeatedly and stopped instead of looping.
- `BLOCKED_UNPAUSED_CLOCK_TICKING` - the initial screen was not safe to think
  from and no deterministic continuation was proven.

Every serious run writes telemetry under `recordings/<run_id>/telemetry/`,
including command spans, timing samples, screenshots when enabled, and the final
summary/frame-delta report when the run ends in a safe state.
If telemetry cannot be initialized at startup, the runner reports
`telemetry_start_exception` before live actions instead of starting an
unrecorded run. If the background screenshot recorder cannot start, it reports
`screenshot_start_exception` and stops with telemetry evidence.
If final screenshot capture or frame-delta generation raises, the runner keeps
the original result and records `screenshot_finalization_exception` or
`frame_delta_report_exception` telemetry for later debugging.
Final frame-report event writes and summary writes are best effort: if either
telemetry write fails during shutdown, the runner still returns the original
success or block result instead of replacing it with a recording failure. When
the frame-report event write fails but summary still succeeds, the summary extra
includes `frame_report_event_error`.
Named exception-stop events such as `pause_guard_initial_exception`,
`preflight_exception`, and `screen_classification_exception` are also best
effort; the returned stop block keeps the original helper error and attaches any
event-write failure under `telemetry_event_errors`.
Progress/status rows such as `runner_progress`, `pace_gate`,
`startup_hidden_panel_handled`, `post_segment_panel_blocked`,
`post_segment_panel_handled`, and `segment_requires_immediate_continuation` are
best effort for the same reason: they should support audits without changing
the actual run, stop, or retry decision.
The final `runner_finish` event write is also best effort; if it fails, the
returned result keeps the original status/reason and includes
`runner_finish_event_error` for the caller.
Command span start/finish telemetry is best effort around helper calls. If the
start row fails, the helper still runs and the returned helper result carries
`command_span_start_event_error`; if the finish row fails, the helper result is
returned with `command_span_finish_event_error`. If a helper raises and the
exception span write also fails, the original helper exception remains
authoritative and the span write failure is carried in `telemetry_event_errors`.
Session-load exception telemetry is best effort too. A failed
`session_load_exception` event write is attached to the returned block as
`telemetry_event_errors` instead of replacing the real session-read failure.
Segment stop evidence is likewise preserved if `segment_result`, `clock_sample`,
or the named stop telemetry event fails to write; the returned block includes
`telemetry_event_errors` while keeping the original stop reason and nested
evidence. The final top-level `telemetry_event_errors` summary deduplicates
errors already present in a nested block, but the nested block keeps its local
copy for context.
If a newly started Lightning timeline cannot rehome telemetry, it records
`telemetry_rehome_exception` and keeps writing into the previous telemetry
directory rather than blocking a safe run solely on recording cleanup. The
old-recorder `telemetry_rehome` start row, old summary, new-recorder
`telemetry_rehome` OK row, `telemetry_rehome_exception`, and
`telemetry_rehome_skipped` rows are themselves best effort; if any write fails,
the pending error is carried in `telemetry_event_errors`.

Standalone recovery command:

```bash
python3 game_loop.py lightning_abandon_to_setup --reason "route_gate_retry"
```

Use it only from a verified pause-safe state. It clicks Abandon Timeline,
confirms, selects the carry-forward pilot, and requires the final visible UI to
classify as `new_game_setup`. On that verified setup return it removes stale
bridge state/command files for the abandoned timeline, so the next run cannot
inherit the old deployment or combat snapshot.
