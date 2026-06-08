# Lightning War Experiments

This log tracks Blitzkrieg Lightning War practice work. Use the pattern:
hypothesis -> segment -> evidence -> result -> derived rule -> code/docs update.

## 2026-06-07 - Detect macOS Privacy Prompt Over ITB

Hypothesis: a macOS screen/audio privacy authorization prompt can visually cover
the ITB pause menu while the Lightning UI classifier mistakes its button crops
for an in-game `perfect_reward_choice` panel. The runner should surface this as
an external user-authorization blocker, not as reward/shop/game UI.

Segment: live baseline validation
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`,
attempt `20260607_053152_168`, followed by
`python3 game_loop.py lightning_ui classify`.

Evidence:
- `lightning_abandon_to_setup --reason first_island_intro_false_positive_patch_cleanup`
  blocked with `abandon_to_setup_pause_failed` because the visible screen was
  classified as `perfect_reward_choice`.
- Visual inspection of `/var/.../itb_lightning_ui_21657.png` showed a macOS
  prompt: `"Codex" is requesting to bypass the system private window picker...`.
- The prompt's strict crop score was only `0.203` because the actual prompt is
  smaller/translucent over the pause menu, but the icon/text evidence was
  distinctive.

Result: `system_privacy_prompt` detection now has a relaxed path requiring the
distinctive privacy icon color, bright prompt text, button gray, and card
evidence. Reclassification of the same live screen returned
`visible_ui: system_privacy_prompt`, `requires_user_authorization: true`, and a
stop message that automation must not click it automatically.

Focused regression:
- `python3 -m py_compile src/loop/commands.py src/loop/lightning_runner.py game_loop.py`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "privacy_prompt or system_privacy_prompt or classifier_detects_macos"`
  passed with `3 passed`.

## 2026-06-07 - Guarded Preview Retry Can Handoff Safe Early Commits

Hypothesis: same-island route retries from an already-open preview need the
calibrated `dialogue-region-repeat-preview-board` path preserved. If a live
preview probe opens turn-zero deployment before the explicit Start click and
the actual mission is not vetoed by Lightning routing policy, that state is a
safe deployment handoff rather than a route mismatch.

Segment: live baseline validations around attempts `20260607_051310_181`,
`20260607_052250_515`, and focused test replays.

Evidence:
- Attempt `20260607_051310_181` still stopped at
  `route_preview_existing_mission_preview_before_region_click` because the
  unknown safe-preview probe had downgraded the start mode to `preview-board`,
  removing the safe reselect suffix.
- After preserving `dialogue-region-repeat-preview-board`, attempt
  `20260607_052250_515` progressed past that gate. The second route probe
  reached turn-zero deployment for `Mission_Survive` before the explicit Start
  click, then blocked as `route_mission_mismatch_after_start`.
- `Mission_Survive` was not vetoed by baseline Lightning route policy, so the
  block was overly conservative for an auto-start-safe preview.

Result: safe preview probes now preserve dialogue/reselect start modes, the
existing-preview suffix can repeat the region after proving the UI is an open
mission preview, and `_lightning_committed_preview_after_click` returns
`route_preview_committed_safe_mission_before_start` for safe early deployment
handoffs. Vetoed/missing missions still write mismatch evidence and recover.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "committed_safe or committed_vetoed or committed_preview or existing_preview or safe_probe or dialogue_region_repeat or route_preview or route_start"`
  passed with `57 passed`.
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
  passed with `549 passed`.

## 2026-06-07 - Clear Active Island Intro False Positives

Hypothesis: first-island intro dialogue can be misclassified as a
`perfect_island_panel` because the bottom-right Continue button and large CEO
panel overlap the post-island reward crops. When live bridge state proves
turn-zero active mission/deployment context, that UI is safe intro dialogue and
should use the bottom-right Continue coordinate, not the Perfect Island
continue coordinate.

Segment: live baseline revalidation
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`,
outer telemetry `lightning_20260607_025801_527`, attempts
`20260607_025811_627`, `20260607_030030_791`, `20260607_030251_303`, and
`20260607_030529_911`.

Evidence:
- Attempts 1-3 safely rerolled after same-island route probes vetoed
  `Mission_Volatile`, `Mission_Satellite`, and `Mission_Airstrike`.
- Attempt 4 selected Detritus and stopped before route planning with
  `pause_after_first_island_not_verified`.
- The guard for `20260607_030529_911` classified the screen as
  `perfect_island_panel`, but bridge refinement recorded `turn=0`,
  `deployment_zone_count=14`, and `in_active_mission=true`.
- The captured screen was Detritus Disposal Head Office intro dialogue with a
  visible bottom-right `CONTINUE` button.

Result: bridge refinement now maps active turn-zero deployment/intro false
positives from `reward_panel` or `perfect_island_panel` to
`bottom_continue_panel` / `bottom_continue`. The preferred-control helper also
recognizes saved bridge-refine evidence for this case, so the panel-clear chain
clicks the bottom-right intro Continue instead of the Perfect Island coordinate.

Focused regression:
- `python3 -m py_compile src/loop/commands.py src/loop/lightning_runner.py game_loop.py`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "active_intro or refine_maps_active_intro or clear_panel_chain_clears_active_intro or prefers_bottom_continue"`
  passed with `5 passed`.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-07 - Retry Preview Blocks When Same-Island Evidence Exists

Hypothesis: the previous preview-retry suppression was too broad. It prevented
unsafe blind retries after a preview opened, but it also forced full timeline
rerolls even when the same route-start result carried distinct candidate
coordinates that could be probed with the same pre-Start validation.

Segment: live baseline run
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`,
outer telemetry `lightning_20260607_023023_353`, rehomed through attempts
`20260607_023036_520` to `20260607_024609_848`.

Evidence:
- No combat was entered after the Airstrike/FreezeBots fixes. Attempts stopped
  pre-Start or recovered to setup on route mismatch, deployment bridge
  uncertainty, or preview vetoes.
- The retry budget was exhausted by conservative route gates: `Mission_Airstrike`,
  `Mission_Dam` mismatch, `Mission_Tanks`, repeated `Mission_Volatile`, and
  final `Mission_Satellite`.
- Final segment `20260607_024609_848` stopped with
  `route_preview_auto_start_vetoed_before_start` for `Mission_Satellite`, even
  though route candidates existed. The segment recorded
  `route_auto_start_retry_suppressed=preview_context_not_map_safe`, then the
  outer runner stopped at `route_auto_start_not_allowed`.

Result: preview-only route blocks now record the rejected candidate, then try a
distinct same-island candidate from the attempt/route-start candidate list before
asking the outer runner to abandon the timeline. The retry still uses
`lightning_route_start` pre-Start validation; vetoed, stale, mismatched, or
unverified previews never click Start Mission. If no distinct candidate remains,
the segment stops with
`route_auto_start_retry_suppressed=no_same_island_retry_candidate`.

Derived rule: same-island retry is allowed only when there is explicit candidate
evidence and the next `lightning_route_start` can revalidate before Start. It is
not a license to board-click through an opened preview.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_auto_start or preview_mismatch or unassigned_multi_region_preview or vetoed_probe_preview or unverified_visual_route or vetoed_visual_preview"`
  passed with `7 passed`.
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
  passed with `531 passed`.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-07 - Veto Airstrike For Lightning Routes

Hypothesis: Archive `Mission_Airstrike` is not reliable for no-surprise
Lightning War routing because its minimum-kill objective can become impossible
before the final End Turn even when grid/building safety is clean.

Segment: live baseline run `20260607_021757_040`, attempt 1 on Archive.
Setup proof passed for Blitzkrieg / Easy / AE off. The route preview validated
`Mission_Airstrike`, deployment succeeded, and combat advanced through turn 2.

Evidence:
- Turn 3 fresh `read` confirmed `Mission_Airstrike`, phase `combat_player`,
  grid `5/7`, one remaining Scarab, and `mission_kills_done=3` from the safety
  summary.
- Fresh `solve` found no clean candidate among 1000. The top plan killed the
  final visible enemy but still ended at `mission_kills_done=4` against target
  `5`, and the lookahead frontier stayed objective-dirty.
- The achievement playbook already treats minimum-kill counters as final-turn
  hard gates for no-failed-objective runs.

Result: route auto-start now explicitly vetoes `Mission_Airstrike` for both
baseline and speed routing. The current safety-blocked timeline should be
abandoned rather than dirty-advanced.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "fragile_objective_missions_auto_start or baseline_route_status"`

## 2026-06-07 - Veto Freeze Bots For Lightning Routes

Hypothesis: `Mission_FreezeBots` is unsafe for autonomous Lightning War route
auto-start because the repo's safety model intentionally treats thawing a
protected Snowtank/Snowlaser as an objective loss.

Segment: live baseline run `20260607_020430_325`, attempt 3 on Pinnacle.
Setup proof passed for Blitzkrieg / Easy / AE off, the route preview validated
`Mission_FreezeBots`, deployment succeeded, and combat advanced bridge-backed
through turn 4.

Evidence:
- Turn 4 fresh `read` confirmed `Mission_FreezeBots`, phase `combat_player`,
  grid `5/7`, and one building threat.
- Fresh `solve` found no clean candidate among 1000. Every candidate was
  `SAFETY_BLOCKED` on `protected_objective_unit_unfrozen` because the predicted
  outcome thawed one protected bot.
- `data/mission_unit_objectives.json` marks `Snowtank` and `Snowlaser` as
  protected for `Mission_FreezeBots`, and `tests/test_plan_safety.py` encodes
  thawing one as a blocking safety loss.

Result: route auto-start now explicitly vetoes `Mission_FreezeBots` for both
baseline and speed routing. The current safety-blocked timeline should be
abandoned rather than dirty-advanced.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "freezebots_auto_start or baseline_route_status_keeps_fragile_mission_vetoes"`

## 2026-06-07 - Suppress Same-Segment Preview Retries

Hypothesis: a route preview gate is not a safe place to probe another visible
red region in the same segment. After the first preview opens, pause/resume no
longer proves the UI is back on the island map, so a second "region" click can
land on the preview/start surface and commit the vetoed mission.

Segment: live baseline run
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
Attempts 1-2 rerolled safely. Attempt 3 on Pinnacle preview-vetoed
`Mission_Satellite`, retried another candidate inside the same segment, then
ended with visible deployment text for `Mission_Satellite` despite the
pre-start veto. The orchestrator recovered by abandoning to setup, but the
route-start contract was unsafe.

Evidence:
- Segment output showed `route_preview_auto_start_vetoed_before_start`, then a
  same-segment `route_auto_start_retry_index`.
- The subsequent pause guard reported `live_snapshot.phase=combat_enemy`,
  `mission_id=Mission_Satellite`, `deployment_zone_count=11`, and OCR text
  `Deploying Lightning Mech`.
- No combat actions were taken; the runner abandoned the timeline and cleaned
  stale bridge files.

Result: `cmd_lightning_segment` now treats preview-only route gates as terminal
for that segment. It records the rejected candidate, marks
`route_auto_start_retry_suppressed=preview_context_not_map_safe`, and returns
`route_auto_start_not_allowed` so the outer runner can restart from a fresh
setup instead of probing another candidate from an uncertain preview context.
The preview-gate reason set is shared by route-start block summarization, and
the runner recognizes stale/mismatch/start-button-missing preview variants as
pre-start gates.

Later note: the 2026-06-07 same-island retry follow-up above narrows this
terminal behavior to cases where no distinct retry candidate evidence remains.
Preview retries are allowed only through another validating `lightning_route_start`
probe, never through an unguarded Start Mission click.

Derived rule: live preview proof is single-use. After any pre-start preview
gate, do not retry another map region until the timeline is safely restarted or
the island map is freshly verified.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
  passed with `530 passed`.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Ignore Stale Pause-Guard Menu Evidence After Route Recovery

Hypothesis: route mismatch recovery can safely return the game to setup or map,
but the outer runner must decide from the newest visible evidence. A stale
`pause_guard` snapshot inside a segment can look like `new_game_setup` even
when route-start resume evidence shows a non-menu handoff.

Segment: live bounded baseline revalidation:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The segment for `recordings/20260606_224809_245` stopped with
`route_mission_mismatch_after_start_recovered`, then the wrapper blocked as
`reload_or_main_menu_visible`.

Evidence:
- Telemetry path `pause_guard.visible_ui.visible_ui` reported
  `new_game_setup`.
- Newer nested evidence at
  `last_attempt.resume_guard.post_click_visible_ui.visible_ui` reported
  `island_map_or_unknown`.
- `lightning_abandon_to_setup --reason stale_pause_guard_menu_evidence_revalidation`
  confirmed the live screen was already `new_game_setup`.

Result: current unexpected-menu detection now ignores `pause_guard` menu/setup
evidence only when a newer resume/post-click classifier already reports a
non-menu visible screen. Direct current `visible_ui: title_screen` or
`visible_ui: new_game_setup` still blocks as reload/main-menu evidence.

Focused regression:
- `python3 -m pytest tests/test_lightning_runner.py -q -k "unexpected_menu_evidence or reload_or_main_menu_visible or route_mission_mismatch or preview_only_route_gate or top_level_preview_only_route_gate or route_gate"`
  passed with `16 passed`.
- `python3 -m pytest tests/test_lightning_runner.py -q` passed with
  `215 passed`.

Code/docs update:
- `src/loop/lightning_runner.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Restart Wrapper Handles Specific Preview Gate Reasons

Hypothesis: after splitting baseline/speed route policy, the lower-level
segment correctly blocks an unassigned multi-region preview when the visible
`Start Mission` button is missing, but the outer autonomous runner still needs
to treat that pre-start route gate as a rerollable attempt instead of resuming
into the unvalidated preview.

Segment: live bounded baseline revalidation:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The segment for `recordings/20260606_224005_699` stopped with
`route_preview_unassigned_multi_region_start_button_missing_before_start`,
then the wrapper resumed from pause and immediately stopped on
`mission_preview_requires_route_validation`.

Evidence:
- No deployment or combat was entered; the stop happened on the mission-preview
  board before Start Mission.
- `lightning_abandon_to_setup --reason autonomous_route_gate_wrapper_reentered_preview`
  safely parked the game back at `new_game_setup`.
- The segment-level reason was the new specific lowercase preview gate rather
  than the older top-level `route_auto_start_not_allowed` token, so the wrapper
  did not enter its route-gate restart path.

Result: the runner now synthesizes restartable `ROUTE_AUTO_START_NOT_ALLOWED`
evidence from preview-only route-gate reasons, including top-level specific
reasons and nested route-start step reasons. Immediate stop handling defers
only for those pre-start route gates, so true unvalidated mission previews
still stop before any Start Mission click.

Focused regression:
- `python3 -m pytest tests/test_lightning_runner.py -q -k "preview_only_route_gate or top_level_preview_only_route_gate or route_gate"`
  passed with `12 passed`.
- `python3 -m pytest tests/test_lightning_runner.py -q` passed with
  `214 passed`.
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "baseline_route_status or visual_route_candidates_use_baseline_policy or unassigned_preview or unassigned_multi_region_auto_preview or speed_route_status_vetoes_mines"`
  passed with `7 passed`.

Code/docs update:
- `src/loop/lightning_runner.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Split Baseline Route Policy From Speed Vetoes

Hypothesis: same-island route retries are working, but baseline auto-start is
still too strict because lower-level route validation applies the broad
Lightning War speed-veto list to `routing=lightning_baseline`. That makes
reasonable baseline missions such as Tides, Cataclysm, and Artillery
reroll-only, so an 8-attempt autonomous baseline can exhaust setup retries
without entering combat.

Segment: live bounded baseline revalidation:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The runner stayed pre-combat and ended blocked at
`recordings/20260606_221004_264/telemetry/summary.md` with
`Reason: route_auto_start_not_allowed`.

Evidence:
- Attempts safely rejected Train, Volatile, Mines, and unassigned multi-region
  previews before Start Mission; no deployment or combat was entered.
- The retry path tried same-island candidates before spending the outer reroll
  budget, but baseline still vetoed speed-slow missions that are acceptable for
  a no-surprise two-island proof.
- The final blocked telemetry summary for `20260606_221004_264` shows baseline
  mode, target islands 2, timer still at `0:00:09`, and no frame drops.

Result: route auto-start validation now distinguishes speed and baseline
policies. Speed mode keeps the historical broad `vetoed_mission:*` policy.
Baseline hard-vetoes protected/counter/repair/volatile/train-style objective
risks, but allows reliable speed-slow candidates such as `Mission_Tides`,
`Mission_Cataclysm`, and `Mission_Artillery`. A later live run showed
`Mission_Airstrike` belongs back in the veto set because of its minimum-kill
counter. Visual route candidates preserve routing, mission tags,
bonus ids, and explicit auto-start veto metadata through save-to-CV assignment.
For unassigned multi-region previews, speed mode still blocks before Start
Mission; baseline mode may commit only if the bridge preview is baseline-safe
and CV finds a visible `Start Mission` button. If that button is absent, it
blocks before the board-click fallback.

Derived rules:
- Baseline reliability policy is not the same as speed policy. Do not reject
  missions merely because they are slow if the solver can model them and they
  do not carry fragile objective surprises.
- Unassigned multi-region baseline preview proof can authorize only the visible
  `Start Mission` button, never a blind preview-board click.

Focused regression:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "baseline_route_status or visual_route_candidates_use_baseline_policy or unassigned_preview or unassigned_multi_region_auto_preview or speed_route_status_vetoes_mines"`
  passed with `7 passed`.
- `python3 -m pytest tests/test_lightning_war_tools.py -q` passed with
  `299 passed`.
- `python3 -m pytest tests/test_lightning_runner.py -q` passed with
  `212 passed`.
- `python3 -m pytest tests/test_mission_picker.py -q` passed with `49 passed`.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Retry Same-Island Route Candidates Before Reroll

Hypothesis: first-island rotation fixed single-corporation tunnel vision, but a
fresh timeline should not be abandoned after the first preview-only route
candidate rejection when the same island map still has another distinct route
candidate to probe safely before Start Mission.

Segment: live bounded baseline revalidation after first-island rotation:
`python3 game_loop.py lightning_abandon_to_setup --reason first_island_rotation_revalidation`,
then
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The runner safely abandoned/restarted every route gate and did not enter
deployment or combat.

Evidence:
- `recordings/20260606_205349_625/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: route_auto_start_not_allowed`.
- Attempt sequence confirmed corporate rotation:
  Archive `Mission_Tides`, R.S.T. `Mission_Survive`, Pinnacle
  `Mission_FreezeBldg`, Detritus `Mission_Artillery`, Archive `Mission_Tanks`,
  R.S.T. `Mission_Satellite`, Pinnacle `Mission_Artillery`, Detritus
  `Mission_Tanks`.
- The first three attempts blocked as
  `route_preview_unassigned_multi_region_before_start`; later attempts were
  baseline/speed vetoes. Each safe route rejection consumed a whole fresh setup
  attempt even when another candidate was available.
- Two startup intro clears produced likely crop-only `kia_panel` classifications
  with no real terminal outcome. They did not stop the run, but they polluted
  evidence and could become false terminal blocks in stricter paths.

Result: `cmd_lightning_segment` now records the rejected auto-start candidate
and tries the next distinct same-island candidate from the latest attempt or
route-start candidate list before returning `route_auto_start_not_allowed` to
the outer runner. The terminal-evidence helpers now require explicit
text/flag/OCR proof for `kia_panel` to count as a terminal outcome when a clean
OCR audit is present; bare unaudited KIA-looking panels still block pause guard
and runner terminal checks.

Derived rules:
- Preview-only route gates should exhaust same-island candidates before spending
  a fresh timeline, as long as no Start Mission, deployment, combat, desync, or
  stop-sign state has occurred.
- A KIA-shaped CV crop is evidence to log, not proof of KIA, when OCR/text audit
  is clean. Real KIA/failed-objective text or terminal flags remain hard stop
  signs.

Focused regression:
`python3 -m py_compile game_loop.py src/loop/commands.py src/loop/lightning_runner.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py && python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q -k 'terminal_visible_ui or ocr_clean_kia or route_auto_start or vetoed_probe or preview_mismatch or unassigned_multi_region_preview or first_island_for_attempt'`
passed with `10 passed`.

Broader regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py tests/test_lightning_autonomous_conductor.py -q`
passed with `581 passed`.

Code/docs update:
- `src/loop/commands.py`
- `src/loop/lightning_runner.py`
- `tests/test_lightning_war_tools.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Rotate First-Island Rerolls Across Corporations

Hypothesis: after unlabeled route-probe rotation is working, repeated
pre-combat route-gate rerolls should not spend the whole attempt budget on the
same first corporate island. A bad Archive mission slate can present only
vetoed missions or unassigned multi-region previews; switching the fresh first
island is safer than weakening route gates.

Segment: live bounded baseline revalidation:
`python3 game_loop.py lightning_abandon_to_setup --reason route_probe_offset_revalidation`,
then
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The runner safely abandoned/restarted every route gate and did not enter combat
or click Start Mission after unsafe preview evidence.

Evidence:
- `recordings/20260606_202749_118/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: route_auto_start_not_allowed`.
- Attempt 2 revalidated route-probe rotation with
  `route_auto_start_index=1`, `route_auto_start_probe_offset=1`.
- The eight Archive attempts blocked on vetoed `Mission_Tanks`,
  `Mission_Dam`, `Mission_Artillery`, and unassigned multi-region
  `Mission_Survive` previews.
- The final event kept `current_island=archive`, `mission_index=0`, and
  `islands_completed=[]`, proving the exhausted budget never reached a
  playable baseline mission.

Result: route-gate restarts now choose the next fresh first island by attempt:
configured preference first, then the remaining safe corporate islands in
`archive`, `rst`, `pinnacle`, `detritus` order. Restart telemetry records both
`current_first_island` and `next_first_island`, and the start helper returns the
chosen island.

Derived rule: a route-gate reroll budget must diversify both the unlabeled
region probe and the corporate mission slate. Safety still wins: the runner
keeps vetoes, exact route matching, and unassigned-preview blocks; it changes
only the next fresh setup choice after a safe abandon.

Focused regression:
`python3 -m pytest tests/test_lightning_runner.py -q -k 'first_island_for_attempt or restarts_route_gate_attempt_from_setup or restarts_preview_only_route_gate_after_route_start or does_not_restart_route_gate_when_attempts_exhausted or strict_route_mismatch_after_start'`
passed with `6 passed`.

Code/docs update:
- `src/loop/lightning_runner.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Rotate Unlabeled Route Probes Across Rerolls

Hypothesis: once preview-only route gates are restartable, repeated fresh
attempts should not always probe visual region index 0 when the map has only
unlabeled red-region candidates.

Segment: bounded live baseline run after the unassigned-preview reroll fix:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 8`.
The runner safely abandoned/restarted each pre-combat route gate and exhausted
the full attempt budget without manual combat decisions or Start Mission clicks
after unsafe preview evidence.

Evidence:
- `recordings/20260606_195819_634/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: route_auto_start_not_allowed`.
- Aggregate telemetry `recordings/lightning_20260606_194239_367/telemetry/events.jsonl`
  shows the runner restarted after the first attempt's
  `route_preview_mission_unverified_before_start` gate.
- Later attempts vetoed Train, Artillery, Volatile, Mines, and Dam previews, and
  one attempt hit `route_preview_unassigned_multi_region_before_start`.
- The final attempt had two detected red regions but the chosen candidate was
  again `route_auto_start_index=0`, with no save-backed mission assignment.

Result: `cmd_lightning_segment` now accepts `route_probe_offset` and applies it
only after candidates with verified mission ids have been considered. Unlabeled
probe candidates rotate by that offset, so fresh setup rerolls and later
session route maps can preview a different visual region without weakening
route vetoes or committing from ambiguous previews. The autonomous runner
derives the offset from attempt number plus persisted mission/island progress.

Derived rule: route-gate rerolls are only useful if they explore more than the
first unlabeled visible blob. Verified mission identity remains the primary
selection signal; rotation is reserved for the no-mission-id probe case.

Focused regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
passed with `546 passed`.

Code/docs update:
- `game_loop.py`
- `src/loop/commands.py`
- `src/loop/lightning_runner.py`
- `tests/test_lightning_war_tools.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Unassigned Preview Gates Are Rerollable

Hypothesis: the new unassigned multi-region preview guard is a pre-Start,
preview-only route gate, so the outer Lightning runner should abandon to
verified setup and reroll instead of ending the whole autonomous attempt while
attempt budget remains.

Segment: bounded live baseline run after the multi-region preview guard:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 4`.
The runner started a fresh Blitzkrieg/Easy/AE OFF attempt and reached an
Archive map with multiple unassigned visible red regions. A preview probe
identified `Mission_Tides`, but because the route had no exact per-region
mission assignment, `lightning_route_start` blocked before Start Mission as
`route_preview_unassigned_multi_region_before_start`.

Evidence:
- `recordings/20260606_191850_252/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: route_auto_start_not_allowed`.
- The segment evidence includes
  `route_auto_start_blocked_candidate.auto_route_block_reason =
  unassigned_multi_region_preview` with `mission_id=Mission_Tides`.
- This was pre-combat and pre-Start; the segment had only preview evidence.

Result: `_segment_preview_only_route_gate` now treats
`route_preview_unassigned_multi_region_before_start` like the other pre-Start
preview gates. While attempt budget remains and no combat signal is present,
the runner abandons to verified setup and rerolls instead of returning a
terminal `route_auto_start_not_allowed` block.

Derived rule: refusing an ambiguous preview commit is not a hard live blocker by
itself. It is a safe RNG/routing reroll, with the same budget and no-combat
limits as vetoed or unverified mission previews.

Focused regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
passed with `542 passed`.

Code/docs update:
- `src/loop/lightning_runner.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Unassigned Multi-Region Preview Must Not Commit

Hypothesis: a live bridge preview can validate a safe mission id for the
currently highlighted region while the later broad Start/board click still
commits a different visible region if the map has multiple unassigned red
regions.

Segment: bounded live baseline run:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 4`.
Attempts 1 and 2 route-gated safely; attempt 3 clicked an unlabeled Archive
region, preview-validated `Mission_Airstrike`, but the Start Mission handoff
loaded `Mission_Dam`. The mismatch recovery abandoned back to verified setup
before deployment and the runner ended blocked.

Evidence:
- `recordings/20260606_190659_642/lightning_route_mismatch.json` records
  `expected_mission_id=Mission_Airstrike`,
  `actual_mission_id=Mission_Dam`, `turn=0`, and
  `deployment_zone_count=11`.
- `recordings/20260606_190659_642/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: reload_or_main_menu_visible`.
- The route plan had two visual red regions but candidate commands lacked
  mission ids, so the segment used a live-preview probe rather than an exact
  save-backed visual assignment.

Result: unlabeled auto-start probes now block before Start Mission when
multiple red regions remain visible and the selected region has no per-region
mission assignment, even if the live preview names a safe mission. Live
`bridge` island-map recommendations that produce multiple unassigned route
candidates now fall back to save/CV route assignment just like ambiguous
`bridge_preview` recommendations. Target hints no longer stamp the same top
mission onto multiple unassigned visual regions.

Derived rule: a safe live preview is not enough proof for a broad commit click
when more than one unassigned red route region is visible. Auto-start needs
either one visible region, a per-region save-backed mission assignment, or a
fresh route-start block and outer setup reroll.

Focused regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
passed with `541 passed`.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Do Not Retry Routes From An Open Preview

Hypothesis: after a preview-only route gate, trying the next visible red region
inside the same `lightning_segment` is unsafe because the pause menu can hide an
open mission-preview or deployment surface rather than a clean island map.

Segment: bounded live baseline run:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2 --max-attempts 4`.
Attempts `20260606_183914_838`, `20260606_184111_602`, and
`20260606_184538_042` all stayed within stop signs and route-gate restart
policy. The runner abandoned/restarted route-gated attempts and ended blocked
after max attempts with no combat/manual decisions.

Evidence:
- Attempt `20260606_183914_838` opened a safe-looking `Mission_Tides` bridge
  preview, but multiple red regions made the forced preview ambiguous. The
  segment stopped at `route_auto_start_not_allowed` and the runner rerolled.
- Attempts `20260606_184111_602` and `20260606_184538_042` probed Artillery
  routes. The route-start helper returned
  `route_preview_auto_start_vetoed_before_start` for `Mission_Artillery`, but
  the pause guard afterward showed the bridge in a pre-combat
  `Mission_Artillery` deployment-like state. The outer runner abandoned safely,
  but the same-segment retry had already clicked another route candidate while
  the underlying screen was no longer proven to be the island map.
- Final telemetry:
  `recordings/20260606_184538_042/telemetry/summary.md` reports
  `Status: BLOCKED`, `Reason: route_auto_start_not_allowed`,
  with timer still `0:00:11`.

Result: preview-only blocks no longer retry another detected red region inside
the same segment. Unlabeled auto previews also force the simpler
`preview-board` route sequence instead of inheriting dialogue-repeat start
modes. The visible map planner now ignores an ambiguous multi-region
`bridge_preview` in favor of save/CV route candidates even when the
save-to-visual assignment is only unlabeled. Route-gated attempts still reroll
from verified setup when the runner has attempt budget remaining.

Derived rule: a route preview block is not a clean map state. Before another
route-region click, automation needs either a proved back-to-map recovery helper
or a fresh verified setup reroll.

Focused regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
passed with 536 tests.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Route Preview Mismatch Must Not Start

Hypothesis: the baseline runner can safely use live preview probes for
unlabeled visible map regions only if a mismatched preview never reaches Start
Mission, and save/profile `region_id` is never treated as a visual click index.

Segment: fresh Blitzkrieg/Easy/AE OFF baseline attempts from setup. Attempts
`20260606_180547_167` and `20260606_180809_937` blocked ambiguous forced bridge
preview routes before Start. Attempt `20260606_181018_121` completed
`Mission_Tides` safely, but the post-mission route handoff targeted
`Mission_Tides` while a later start loaded `Mission_Artillery`; the runner
strictly blocked and restarted. Attempts around `20260606_182154_259` and
`20260606_182532_873` then vetoed visible `Mission_Artillery` previews before
Start and parked safely.

Evidence:
- Fresh `read` plus `solve` after recovery produced a clean turn-3
  `Mission_Tides` plan, and `auto_turn --time-limit 10` completed without a
  safety block.
- Reward OCR after that combat showed `Region Secured`, `Protect the Coal
  Plant`, and `Civilians Protected`, with no KIA or failed-objective text.
- The route layer later used a save `top_region_id` as visual index `6`, then
  retried visual index `0` and reached the wrong mission path.

Result: route auto-start now refuses to synthesize a visual candidate from
save/profile region ids. A route preview mismatch before Start is converted into
a rejected visible candidate without committing. If a wrong mission still loads
after Start, route-start writes mismatch evidence, attempts deployment-screen
recovery when possible, and blocks instead of continuing a different mission.

Derived rule: live preview probes are allowed as observation, not commitment.
Only CV-detected red-region candidates may be clicked, and only bridge-verified
mission identity may authorize Start Mission.

Focused regression:
`python3 -m pytest tests/test_mission_picker.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`
passed with 536 tests.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-06 - Train Is Not Baseline-Safe

Hypothesis: the reliable two-island baseline should not use the raw
Lightning War speed preference for Train missions until the end-to-end baseline
is proven.

Segment: fresh Blitzkrieg/Easy/AE OFF baseline attempt
`20260606_172153_821`, Archive first island. Route auto-start selected
`Mission_Train`, deployed cleanly, and completed turn 1. On turn 2 the solver
stopped with `SAFETY_BLOCKED`.

Evidence:
- `recordings/20260606_172153_821/m00_turn_02_solve.json` reports all sampled
  candidate classes in the dirty frontier as `objective_loss`.
- The blocking safety violation is `protected_objective_unit_lost` for
  `Train_Pawn` at bridge `[4, 4]`.
- The runner did not click End Turn after the safety block and returned the
  stop-sign next step for dirty-frontier review.

Result: `Mission_Train` remains eligible for raw speed-mode experimentation,
but baseline routing now uses `routing=lightning_baseline`, applies a strong
train score penalty, and emits `baseline_reliability_veto:train` so route
auto-start rerolls/blocks instead of entering the mission.

Derived rule: baseline reliability outranks raw speed. Do not start Train in
the two-island proof unless a future solver/routing change proves the protected
train objective can be handled without dirty-plan consent.

Code/docs update:
- `src/strategy/mission_picker.py`
- `src/loop/commands.py`
- `src/loop/lightning_runner.py`
- `tests/test_mission_picker.py`
- `tests/test_lightning_war_tools.py`
- `tests/test_lightning_runner.py`
- `docs/agent/lightning-war-runner.md`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-03 - Outer Watchdog Evidence Tightening

Hypothesis: the high-level Python conductor can safely decide whether Codex may
think only if it understands the nested `lightning_pause_guard` result, not just
the top-level `status/reason`.

Segment: offline focused tests while the live run was parked in verified pause.
No combat or UI progression was executed.

Evidence:
- `lightning_ui guard_status` reported `status: OK`, `visible_ui: pause_menu`,
  and a persisted guard JSON before and after the test/edit window.
- `python -m pytest tests\test_lightning_war_conductor.py` passed.
- `python -m pytest tests\test_lightning_war_tools.py` passed.

Result: the outer watchdog now records nested pause-guard evidence, including
post-click `pause_verify`, screenshot paths, classifier crop scores, live bridge
snapshot summaries, timer probes, and the guard JSON path. A bare
`reason=pause_clicked` is no longer treated as safe without classifier or timer
stop proof.

Derived rule: for Lightning War, `safe_to_think=true` requires verified pause or
a proven non-live screen. A click label alone is not proof. When the lower guard
returns a `last_poll`, the conductor must inspect that nested payload because it
contains the real CV/timer proof.

Code/docs update:
- `scripts/lightning_war_conductor.py`
- `tests/test_lightning_war_conductor.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-04 - R.S.T. Train Preview Dialogue Masks Start Mission

Hypothesis: the R.S.T. `Test Site Echo` Train preview was safe to start, but
`lightning_segment` stopped because the advisor textbox hid the yellow Start
Mission text and the classifier reported `island_map_or_unknown`.

Segment: paused micro-peek and focused classifier fix while the visible game was
verified in the pause menu.

Evidence:
- `lightning_peek route_choice_rst_train_dialogue_current` captured
  `run_notes/lightning_war_smoke_2026-06-04/screenshots/019_route_choice_rst_train_dialogue_current.png`.
- The screenshot showed `Test Site Echo`, `Defend the Train`, an advisor
  textbox, and no visible yellow Start Mission text.
- Direct classifier check on the screenshot now returns
  `mission_preview_panel` with `recommended_control=dialogue_textbox`.

Result: the classifier detects mission-preview cards masked by advisor
dialogue, recommends `dialogue_textbox` first, then lets the existing segment
loop re-read and start the mission. The no-bridge attempt branch now clicks
mission-preview dialogue/start controls locally instead of stopping at a
Codex-facing `visible_panel_without_bridge`.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "lightning_ui_classifier or mission_preview_dialogue"`
passed.

Derived rule: mission-preview dialogue is live and pauseable, not a route-ready
map. Dismiss the textbox inside local automation, then start the preview; do not
return to Codex between those actions.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Blitzkrieg R.S.T. Timer Overrun

Hypothesis: with pause-before-solve and fast route helpers, an Archive + R.S.T.
Blitzkrieg run could still finish under `current.time < 0:30:00` if combat
threat-audit blocks were cleared deterministically.

Segment: live Lightning War attempt `20260604_102343_862`. Archive completed,
R.S.T. reached `Mission_Trapped`, `Mission_Cataclysm`, `Mission_Bomb`, then
opened `Mission_Wind` while the save timer showed about `0:28:24`.

Evidence:
- `Mission_Cataclysm` turn 3 blocked on a new-current Beetle threat at F4
  targeting F5. F4 was in lethal Cataclysm danger, so the attacker died before
  Vek attacks. The audit only blocked because current threats missing from the
  solve-time set were always treated as live.
- After `Mission_Bomb`, the save route assignment pointed visual index 2 at
  `Mission_Wind`, but the live bridge preview for that same region exposed
  `Mission_DungBoss` with `forced_boss_route`. The stale expected mission id
  blocked Start Mission, and the later resume/start flow entered `Mission_Wind`
  instead.
- `Mission_Wind` turn 2 blocked on Scorpion1 at G6 targeting G5. The bridge
  exported `environment_wind_dir=0`, and G6 was in the wind row; Rust predicted
  the gust pushed the Scorpion to F6 before attacks, preserving grid/buildings.
- The attempt exceeded the authoritative save/profile `current.time` budget at
  `0:30:16` and was parked in verified pause.

Result: attempt abandoned as over budget. Three deterministic fixes were added:
new current threats now receive normal coverage analysis, `Mission_Wind` threat
audit projects pre-attack gust movement, and a live bridge boss preview can
override a stale save-map expected route target.

Derived rules:
- For `Mission_Cataclysm`/Seismic, a new current attacker on lethal
  environment is covered if the standard threat-audit environmental-kill logic
  proves it dies before attacks.
- For `Mission_Wind`, threat audit must treat wind rows as pre-attack pushes,
  not direct damage and not live threats when the projected attack no longer
  hits a building.
- When the preview bridge says the selected region is a boss with
  `forced_boss_route`, trust that live preview over stale save assignment and
  start it immediately.
- At or after `current.time >= 0:30:00`, stop the attempt, park in verified
  pause/setup, and restart rather than continuing a dead timeline.

Focused regression:
`python -m pytest tests\test_threat_audit.py tests\test_lightning_war_tools.py -q -k "threat_audit or route_start_accepts_live_boss_preview_over_stale_expected or route_start_blocks_preview_mismatch_before_commit or route_start_commits_matching_preview"`
passed.

Code/docs update:
- `src/solver/threat_audit.py`
- `src/loop/commands.py`
- `tests/test_threat_audit.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Route Mismatch Auto-Abandon Killed Attempt

Hypothesis: exact mission guards should protect against stale preview clicks,
but once Start Mission has already loaded a playable mission, abandoning the
timeline is more expensive than accepting the actual mission.

Segment: Blitzkrieg/Easy/AE Lightning War attempt. R.S.T. was secured first at
about `0:18:59` after Terratide/Test Site Echo, Train/Razor Shore, Bomb/QA
Division, an extra scrapyard/train/filler path, and the Shaman boss. The second
island intro reached Detritus at about `0:20:46`.

Evidence:
- `lightning_segment --route-auto-start` proposed visual region index `0` as
  `Mission_Belt`.
- The explicit route-start command carried
  `--route-target-mission-id Mission_Belt`, but the loaded mission was
  `Mission_Missiles`.
- The route mismatch handler treated this as terminal, deployed, paused, used
  Abandon Timeline, confirmed, and selected a carry-forward pilot. The run
  ended as Timeline Lost with only one island secured.
- The calibrated `abandon_pilot_slot` at window `(490,329)` clicked between
  portraits on Windows. A follow-up Timeline Lost panel showed the first
  carry-forward pilot center at window `(500,329)`.
- Steam sync after the failed attempt still showed Lightning War locked.

Result: the route-start mismatch policy now distinguishes playable mismatches
from hard vetoes. If the post-start bridge snapshot is an active mission with
grid power remaining and the actual mission is not a Lightning hard-veto
mission, the conductor records a warning and continues with the actual loaded
mission as the expected guard. Hard-veto or non-playable mismatches still use
the block/recovery path. The carry-forward pilot calibration was moved to
window `(500,329)`.

Derived rules:
- A post-start exact-target mismatch is not automatically fatal. Continue a
  loaded playable mission rather than spending a failed timeline.
- Do not abandon on a playable mismatch just because the intended route was
  different; the clock already paid the mission-start cost.
- Hard-veto actual missions remain exceptions because their friction can still
  invalidate the Lightning War route.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "post_start_mismatch or playable_route_mismatch or abandon_pilot"`
passed.

Code/docs update:
- `src/loop/commands.py`
- `src/control/mac_click.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-04 - Archive Airstrike Into Forced Forest Fire Restart

Hypothesis: the first Archive slate after setup could still be viable if the
first mission was playable and the conductor recovered from stale map routing.

Segment: Blitzkrieg/Easy/AE fresh attempt, Archive first island. The first
right-side region loaded `Mission_Airstrike` and completed at about `0:04:03`
with grid `5/7`.

Evidence:
- After `Mission_Airstrike`, bridge/save routing exposed only one available red
  mission: `Mission_ForestFire` at Chronology Hall, score `-125`.
- `Mission_ForestFire` remains a Lightning War hard veto because of the fire
  counter objective and prior post-enemy/classifier mismatch.
- The attempt was abandoned from verified pause with 0 islands secured.
- The Timeline Lost carry-forward pilot center on this layout was window
  `(500,329)`, not `(430,329)`.

Result: restart this slate rather than spending a timed attempt on forced
Forest Fire. The Windows `abandon_pilot_slot` calibration is now `(500,329)`.

Derived rule: if a first-island Archive path collapses to forced Forest Fire
after the first mission, abandon/restart from verified pause. Do not route into
Forest Fire for Lightning War unless the known post-enemy issue is fixed.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "abandon_pilot"`
passed.

Code/docs update:
- `src/control/mac_click.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Dirty Consent Survives Pre-Action Resume Failure

Hypothesis: dirty consent should be single-use only after the reviewed dirty
line changes live combat state. A stale heartbeat or failed pause-menu resume
before the first bridge action should not burn the token.

Segment: Lightning War R.S.T. mission 3, turn 2, Mission_Bomb. The reviewed
rank-2 line predicted only nonlethal `mech_hp_loss` with grid at `6/7`, but
the first rerun started while the pause menu was still open. The bridge
heartbeat went stale before any sub-action completed.

Result: `cmd_auto_turn` now validates the exact dirty consent up front with
`consume=False`, stores the pending ID, and marks it used only after a
successful bridge acknowledgement for move/attack/repair/skip. Failed resume or
stale heartbeat before action progress leaves the token reusable for the same
unchanged board.

Derived rule: in live Lightning War, consent is a progress boundary, not a
solve boundary. Spend the token when the game accepts the first command, never
while Codex or the conductor is still trying to dismiss pause or regain a live
heartbeat.

Focused regression:
`python -m pytest tests\test_auto_turn_state.py::test_dirty_consent_validation_can_delay_token_consumption tests\test_auto_turn_state.py::test_dirty_consent_progress_mark_consumes_delayed_token -q`
passed. Broader focused suites:
`python -m pytest tests\test_auto_turn_state.py tests\test_lightning_war_tools.py -q`
passed.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_auto_turn_state.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-04 - Hard-Veto Preview Guard Before Start

Hypothesis: after the ambiguous bridge-preview fix, a no-target visual route
start can still commit a mission whose hidden bridge preview is bad for
Lightning War. The helper must split the region preview click from the final
Start Mission click and classify the actual preview mission before committing.

Segment: fresh R.S.T. first-island attempt from verified Blitzkrieg/Easy/AE
setup. Excavation Site completed quickly as `Mission_Volatile`, then the next
manual visual route start selected a red region labeled Central Museums.

Evidence:
- The selected region loaded `Mission_Dam`, not a low-friction mission.
- Turn 2 required reviewed nonlethal dirty consent:
  `b034b38b23e2c785`.
- Turn 3 dirty frontier included `mech_lost`, with consent id
  `b03abedc4fb4a3d4`, which is outside standing consent.
- The attempt was abandoned back to `new_game_setup` before spending the
  Lightning War clock on an unauthorized lethal line.

Result: `cmd_lightning_route_start` now validates every live route start with
an intermediate bridge-preview sample before clicking Start Mission. If the
preview mission id is unavailable, it blocks and verifies pause. If no exact
expected mission was supplied and the preview is one of
`Mission_Artillery`, `Mission_Dam`, `Mission_ForestFire`, or
`Mission_Volatile`, it blocks before Start Mission and verifies pause.

Derived rule: a manual visual region click is not a license to start whatever
the preview hides. For Lightning War, preview first, require a bridge mission
id, and hard-veto known slow or high-friction missions unless an exact route
target explicitly chose them.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "route_start or route_ready or route_auto_start or ambiguous_bridge_preview or visual_route"`
passed.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Island-Complete Leave Screen False Reward/KIA

Hypothesis: the first-island completion screen can be misclassified as a KIA or
perfect-reward panel because the dimmed island map and lower spend/leave panel
overlap the broad reward crops.

Segment: Blitzkrieg Easy AE ON R.S.T. practice attempt, parked after the
Corporate Island completion sequence. The visible screen showed `SPEND
REPUTATION` and `LEAVE ISLAND`, but the classifier reported
`perfect_reward_choice`/`kia_panel`, causing repeated reward-style clicks instead
of leaving the island.

Evidence:
- Verified pause guard classified the top-level rest state as `pause_menu` over
  the completed-island spend/leave screen.
- The underlying screen had no KIA copy or pilot-loss affordance; it was the
  normal island-complete action choice.
- The Lightning clock continued to rise during repeated misclick recovery, so
  the practice attempt became nonviable for a sub-30:00 two-island route.
- Focused regression:
  `python -m pytest tests\test_lightning_war_tools.py -q -k "island_complete_leave or lightning_ui_classifier"`
  passed after adding the explicit classifier case.

Result: the UI classifier now recognizes the completed-island leave button when
it appears over a colored island map. The panel clear path treats it as a
must-act live state and clicks `leave_island`, then immediately clicks
`leave_confirm_yes` if the first click succeeds.

Derived rule: after a Corporate Island completion, do not route the spend/leave
screen through generic reward handling. If `LEAVE ISLAND` is visible, the local
automation owns both leave and confirmation before returning to Codex or the
next route segment.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - HQ Warning And Forced Preview Ambiguity

Hypothesis: the failed R.S.T.-first practice run exposed two deterministic
state bugs: the Corporate HQ warning map was classified as a perfect reward
choice, and Archive route auto-start treated one stale bridge-preview mission as
safe across multiple visible red regions.

Segment: live Lightning War attempt from verified setup, R.S.T. first, then
manual Archive handoff after the R.S.T. boss.

Evidence:
- R.S.T. island plus Corporate HQ completed, but the clock reached about
  `0h 22m 31s`, leaving too little margin for a full second island.
- The HQ warning screen visibly showed the island map with red Corporate HQ and
  a warning tooltip, while the classifier returned `perfect_reward_choice` and
  recommended a Grid reward click.
- Archive route auto-start saw a single `bridge_preview` recommendation for
  `Mission_Tides`, detected two visual red regions, attached the same forced
  preview mission to both, clicked region 0, and loaded
  `Mission_Armored_Train`.
- The mismatch guard correctly did not continue the wrong mission; it abandoned
  the timeline and returned to `new_game_setup`.

Result: island-map classification now wins when substantial red map territory is
visible, even if a tooltip crop looks like a reward button. Forced
bridge-preview routes remain auto-startable only when exactly one visual red
region is present; otherwise candidates are emitted but marked
`auto_route_allowed=false`.

Derived rules:
- A red/green island map plus HQ warning tooltip is `island_map`, not
  `perfect_reward_choice`.
- A single bridge-preview mission is not enough to click one of multiple
  unmapped visible regions. Use save-backed visual assignment, a verified
  single-region preview, or stop at a safe route decision.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q` passed.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Fresh Start Island Handoff Needs Pause Proof

Hypothesis: starting the run and then issuing a separate Codex command to choose
the first corporation can still spend timer between tool boundaries. The local
conductor should own the whole Start -> corporation -> intro Continue -> Pause
handoff and verify the resting state before returning.

Segment: focused unit implementation while the visible game was parked on the
non-live new-game setup screen.

Evidence:
- `lightning_ui` supports ad-hoc `+` sequences, and the calibrated R.S.T.
  controls already include settle times for island selection, intro Continue,
  and Pause.
- `python -m pytest tests\test_lightning_war_conductor.py -q` passed after
  adding a `--start-island rst` path.

Result: `scripts/lightning_war_conductor.py --start-from-verified-setup
--start-island rst` now syncs, verifies setup, clicks the timer-starting modal
Start, selects R.S.T., clears the intro panel, clicks Pause, runs a pause guard,
and only then enters the segment loop.

Derived rule: after the final setup Start, Codex must not own first-island
selection. Use the conductor start-island handoff for fresh R.S.T./Archive
starts, and treat any failed pause proof after the handoff as `must_act_now`.

Code/docs update:
- `scripts/lightning_war_conductor.py`
- `tests/test_lightning_war_conductor.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Sticky Confirm During Route Mismatch Recovery

Hypothesis: after a route mismatch is discovered post-Start, the recovery path
may need more than one deployment CONFIRM click before the first player turn is
pauseable.

Segment: R.S.T. Lightning War attempt after three secured missions. Route handoff
targeted `Mission_Train` at visual region index 0, but post-Start deployment
loaded `Mission_Solar`.

Evidence:
- `lightning_segment` wrote `lightning_route_mismatch.json` with
  `expected_mission_id=Mission_Train` and `actual_mission_id=Mission_Solar`.
- The automatic recovery deployed all three mechs and clicked
  `deploy_confirm`, but pause verification still classified the screen as
  `deployment_screen` with `recommended_control=deploy_confirm`.
- A second standalone `lightning_ui deploy_confirm` followed by
  `lightning_ui ensure_pause` reached a verified `pause_menu`.
- The timeline was then abandoned from the pause menu and the screen returned
  to `new_game_setup`.

Result: post-start mismatch recovery now treats a blocked pause whose visible
UI is `deployment_screen` and recommended control is `deploy_confirm` as a
sticky CONFIRM state. It retries CONFIRM once, waits briefly, and retries pause
before returning control to Codex.

Derived rule: recovery from a mismatched deployment is still local automation's
job. Do not return live from a sticky deployment-confirm state; repeat CONFIRM
once and verify pause before abandoning.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-03 - Post-Start Route Mismatch Recovery

Hypothesis: the route-start path can still click visible Start while the bridge
preview is stale, causing deployment to load a different mission than the
validated route target.

Segment: Blitzkrieg Easy AE ON fresh attempt. Archive route auto-start targeted
and preview-validated `Mission_Tides`, but after Start the live deployment
snapshot reported `Mission_Airstrike`.

Evidence:
- `lightning_segment` stopped with
  `reason=route_mission_mismatch_before_deploy` and persisted
  `recordings/lw/lightning_route_mismatch.json`.
- Deployment had no usable pause/back state. Gear click and Escape both left the
  screen in deployment with the timer advancing.
- Minimal recovery worked: `deploy_recommended`, `deploy_confirm`,
  `lightning_ui ensure_pause`, `abandon_timeline`, `abandon_confirm_yes`, and
  `abandon_pilot_slot` returned the game to `new_game_setup`.
- Focused regression:
  `python -m pytest tests\test_lightning_war_tools.py -q` passed after adding
  a post-Start mismatch recovery test.

Result: `cmd_lightning_route_start` now samples `_lightning_live_snapshot()`
immediately after a successful Start click. If the started mission id differs
from the route target, it writes the mismatch block and, for turn-0 deployment,
locally performs the proven deploy-confirm-pause-abandon recovery before
returning to Codex.

Derived rule: route-start must not return control across an LLM/tool boundary
from a live mismatched deployment. If the one-way Start click already happened,
the local Python command owns recovery to a verified safe state.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`

Follow-up: the Archive map screenshot
`itb_lightning_map_peek_10752.png` showed Preserved Farms and Historic County
touching as one connected red mask. The visual detector clicked the combined
center at Preserved Farms, starting `Mission_Airstrike` while the save route
target was lower Historic County / `Mission_Repair`. A lightly-eroded red mask
now separates adjacent mission regions before visual-to-save assignment. On the
captured map it reports two regions:
- index 0: upper Preserved Farms center around `(809, 420)`.
- index 1: lower Historic County center around `(949, 588)`.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q` passed with the
adjacent-region split test.
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-03 - Setup Screen False Pause Positive

Hypothesis: the `bridge_snapshot_unavailable` practice stop was caused by
starting an instrumented segment from the new-run setup screen while the
Lightning UI classifier mislabeled that setup screen as `pause_menu`.

Segment: `python scripts\lightning_war_conductor.py --max-segments 1
--segment-steps 6 --time-limit 2 --max-wall-seconds 240 --settle-seconds 0`.

Evidence:
- The segment stopped safely with `reason=bridge_snapshot_unavailable` and
  `pause_guard` still safe.
- `lightning_peek bridge_unavailable_pause` captured
  `run_notes/lightning_war_smoke_2026-06-03/screenshots/023_bridge_unavailable_pause.png`.
- The screenshot visibly showed the Blitzkrieg new-run setup screen with Back
  and Start buttons, not the in-game pause menu.
- After the classifier patch, that screenshot classifies as `new_game_setup`
  with strong Back/Start crop scores.

Result: `new_game_setup` detection now runs before pause-menu detection. This
prevents the conductor from trying to resume a setup screen as though it were a
paused live run.

Derived rule: setup is safe to think because the Lightning clock has not started
or the run is parked before Start, but it must be named explicitly. Do not rely
on a generic dark-overlay pause-menu score when the setup Back/Start layout is
visible.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-03 - Timer Start Must Be Inside Conductor

Hypothesis: after the final Difficulty Setup modal passes verification, a
separate Codex-issued Start click followed by a separate conductor command would
spend live achievement time between tool boundaries.

Segment: offline/unit implementation while the visible game was parked on the
verified Difficulty Setup modal.

Evidence:
- `verify_setup --difficulty 0` passed for Easy and all Advanced Content rows.
- `tests/test_lightning_war_conductor.py` passed after adding a
  `--start-from-verified-setup` path.

Result: the outer conductor can now sync, verify the setup modal, click the
timer-starting setup Start button, and immediately enter `lightning_segment
--no-preflight` inside the same Python process.

Derived rule: never let Codex own the gap between final setup Start and the
first island/route action. Use `scripts/lightning_war_conductor.py
--start-from-verified-setup` from the verified modal.

Follow-up: the squad-screen Start control is `setup_start`; the Difficulty Setup
modal's timer-starting button is `setup_modal_start`. The conductor must use the
modal control after `verify_setup` passes.

Code/docs update:
- `scripts/lightning_war_conductor.py`
- `tests/test_lightning_war_conductor.py`
- `docs/agent/lightning-war-experiments.md`

## 2026-06-04 - R.S.T. -> Archive Practice Run Over Budget

Hypothesis: a two-island Blitzkrieg attempt could still recover after first
island routing drift if the second island stayed on fast missions and the
segment loop owned all live states.

Segment: live R.S.T. first island into Archive second island, using
`lightning_segment` with `--pause-between-actions` and manual route starts from
verified pause.

Evidence:
- First island completed, but the run reached Archive mission 6 at
  `current.time=0:25:22`, leaving only `0:04:38`.
- A manual explicit visual route start intended for `Mission_Armored_Train`
  loaded `Mission_ForestFire` because no `--route-target-mission-id` guard was
  supplied to the segment command.
- `Mission_ForestFire` turn 2 produced `INVESTIGATE_POST_ENEMY`: the simulator
  predicted all enemies cleaned up and no mech fire, while the bridge reported
  one enemy alive and WallMech unexpectedly on Fire. Record:
  `recordings/lw/m06_turn_02_post_enemy.json`.
- A pause-before-solve guard returned `live_combat_phase` after the conductor
  had already reached an actionable combat player turn; the segment stopped
  live until restarted.
- A dirty consent token was consumed by a stale-heartbeat `auto_turn` attempt
  before any action executed. A new candidate-rank token succeeded through
  `lightning_segment`.

Result: practice attempt abandoned as non-viable. Current code now treats
explicit visual route starts without a supplied mission id as route-checked:
the route helper infers the save-ranked target and validates the mission preview
before Start Mission. The combat loop also falls through from
`live_combat_phase` pause-guard failure to an immediate no-wait solve instead
of stopping live. Forest Fire gained an additional Lightning War routing
penalty for post-enemy/classifier friction.

Derived rules:
- Manual route commands should include the generated
  `--route-target-mission-id`; if omitted, the segment must infer and enforce
  the target before committing Start Mission.
- `live_combat_phase` from the pause guard during combat is not a safe stop; it
  means the conductor should solve from the fresh bridge state now.
- Forest Fire is avoid-unless-forced for Lightning War until the post-enemy
  fire/enemy cleanup mismatch is diagnosed and regressed.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "forest_fire_friction or live_combat or explicit_visual_start or auto_starts_scored_primary_route"`
passed.

Code/docs update:
- `src/loop/commands.py`
- `src/strategy/mission_picker.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - Ambiguous Bridge Preview Route Guard

Hypothesis: a bridge-preview mission id is not enough to route by exact target
when the visible map has multiple red regions and save-backed region assignment
is unavailable.

Segment: fresh Archive start from verified Blitzkrieg/Easy/AE setup. The
conductor selected Archive, cleared the intro, and reached the island map at
`current.time=0:01:26` with two red regions visible.

Evidence:
- The only bridge-preview candidate was `Mission_Volatile`.
- Visual region 0 clicked Central Museums, but the mission loaded as
  `Mission_Artillery`.
- The route mismatch guard recovered by abandoning to `new_game_setup` before
  deployment/combat. Record:
  `recordings/20260604_060138_355/lightning_route_mismatch.json`.

Result: ambiguous bridge-preview-only route candidates no longer emit
`--route-target-mission-id` or `--expected-mission-id`. Save-backed assignments
and single-region forced previews keep exact guards.

Derived rule: when there are multiple red regions and only a single
bridge-preview candidate, treat that candidate as stale-prone. Do not infer an
exact mission target for every visual region; either choose a visible region
without a target guard and accept the loaded mission, or wait for save-backed
assignment.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "ambiguous_forced_bridge_preview or single_forced_bridge_preview or route_start_uses_visual_region_index or starts_selected_visual_route"`
passed.

Code/docs update:
- `src/loop/commands.py`
- `tests/test_lightning_war_tools.py`
- `docs/agent/lightning-war-experiments.md`
- `docs/agent/lightning-war-state-atlas.md`

## 2026-06-04 - R.S.T. Boss To Archive Timer Miss

Hypothesis: a late first-island boss can still be converted into a two-island
Lightning War if the conductor keeps acting through stale bridge/map states.

Segment: Blitzkrieg/Easy/AE attempt `20260604_163332_450`. R.S.T. boss was
started around `current.time=0:21`, completed, and the conductor reached
Archive `Mission_Tanks`, but the clock exceeded `0:30:00` on Archive turn 4.

Evidence:
- After R.S.T. HQ, the visible screen was the island map / island select while
  bridge/save residue still reported `phase=unknown`, deployment zones, and an
  active mission. The old branch repeatedly tried deployment from that stale
  state.
- The run reached Archive selection around visible `0:25:35`; Archive mission
  1 reached `current.time=0:29:15` at turn 4 and then budget-exceeded at
  `0:30:11`.
- `Mission_Tanks` repeatedly produced post-enemy investigations where Leaper
  web status and later nonlethal mech HP damage differed from the simulator,
  but grid/building/objective state remained viable.

Result: timeline abandoned from a verified pause/new-setup state. The conductor
now treats a visibly confirmed island map as stronger than stale active-mission
or deployment residue, returning route candidates instead of redeploying. Raw
coordinate starts may bypass unverified preview only when there is no exact
expected mission guard, and save-backed exact preview matches are accepted.

Derived rules:
- If visible UI is `island_map` or `island_map_or_unknown`, stale
  `session.current_mission`, `in_active_mission`, or deployment-zone residue is
  a warning, not permission to deploy.
- A first island reaching boss after about `0:20` is not viable unless the boss
  and second island are exceptionally fast; restart is preferred once parked.
- For Lightning War speed only, nonlethal mech HP loss with grid above zero is
  an acceptable dirty loss, but grid/building/objective loss is not.
- Leaper web post-enemy investigations can be cleared only from the fresh live
  bridge state with an explicit reason and no grid/building/objective delta.

Focused regression:
`python -m pytest tests\test_lightning_war_tools.py -q -k "lightning_speed_loss_policy or route_start_raw_coordinates_can_force_unverified_preview or route_start_accepts_explicit_save_backed_preview_match"`
passed before the attempt.

## 2026-06-06 - Recovered Route Mismatch Setup KIA False Positive

Hypothesis: after a route click starts the wrong mission and the recovery path
abandons safely to setup, nested CV metadata from the recovery can contain
transient `kia_panel` labels that are not terminal outcome proof.

Segment: baseline autonomous wrapper attempt `20260606_231251_721`, Detritus
first island. The route preview expected `Mission_Tides`; the live bridge after
Start Mission reported `Mission_Volatile` at turn 0 with deployment zones and no
mechs deployed.

Evidence:
- `recordings/20260606_231251_721/lightning_route_mismatch.json` recorded
  `expected_mission_id=Mission_Tides`, `actual_mission_id=Mission_Volatile`,
  `phase=combat_enemy`, and `deployment_zone_count=10`.
- The mismatch recovery returned to `new_game_setup`.
- The telemetry frame tagged `kia_detected` was visually the new-run setup /
  pilot selection screen, not a KIA panel.

Result: UI metadata strings such as `visible_ui=kia_panel` and
`recommended_control=kia_understood` no longer count as generic KIA stop-token
evidence. Recovered route mismatches are handled as route-mismatch gates:
restart from verified setup while attempts remain, or block clearly as
`route_mission_mismatch_after_start` when attempts are exhausted.

Focused regressions:
- `python3 -m pytest tests/test_lightning_runner.py -q -k "stop_token_evidence or unexpected_menu_evidence or reload_or_main_menu_visible or route_mission_mismatch or preview_only_route_gate or top_level_preview_only_route_gate or route_gate"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "baseline_route_status or visual_route_candidates_use_baseline_policy or unassigned_preview or unassigned_multi_region_auto_preview or speed_route_status_vetoes_mines or route_mismatch"`

## 2026-06-06 - Baseline Route Policy Over-Vetoed Solver-Proved Missions

Hypothesis: the reliable baseline should not use the same broad avoid-list as
Lightning War speed mode. If the route handoff can validate the mission id, the
baseline can let the Rust solver and normal safety gates prove Dam/Mines/Train
turns instead of rerolling the whole timeline before combat starts.

Segment: baseline autonomous wrapper run `20260606_232815_492`.

Evidence:
- Archive attempt: both visible route candidates previewed as `Mission_Mines`,
  so the segment stopped at `route_auto_start_not_allowed` and safely abandoned
  to setup.
- R.S.T. attempt: both visible route candidates previewed as `Mission_Dam`,
  again stopping at `route_auto_start_not_allowed` before deployment.
- Pinnacle attempt: the top route reached `Mission_FreezeBots` but then stopped
  on `deployment_bridge_state_uncertain`, proving the wrapper recovered safely
  but was spending attempts before getting a baseline combat sample.

Historical result: baseline temporarily stopped hard-vetoing `Mission_Dam`,
`Mission_Mines`, or `Mission_Train` by mission id so the solver could gather
combat evidence. This was later narrowed by live proof: `Mission_Dam` and
train variants are again baseline-vetoed, `Mission_Mines` remains allowed
through normal safety gates, and speed mode still uses its narrower route
policy.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "baseline_route_status or visual_route_candidates_use_baseline_policy"`

## 2026-06-06 - Paused Intro Panel Chain Blocked After One Clear

Hypothesis: post-segment panel recovery must keep clearing safe chained panels
until pause is verified. A single safe-panel click is not enough when an island
intro or reward tail produces multiple continuation panels before the game is
pauseable again.

Segment: baseline autonomous wrapper run `lightning_20260606_234321_207`.

Evidence:
- The wrapper resumed from a paused interrupted state with no bridge heartbeat.
- After resume, the visible screen was the Detritus intro CEO dialogue with a
  `CONTINUE` button, but CV labeled it `perfect_island_panel`.
- The safe-panel handler clicked once, then `ensure_pause` returned
  `visible_panel_should_be_cleared_first`; the old runner blocked as
  `post_segment_panel_blocked` instead of clearing the next safe panel.

Result: the paused post-segment panel handler now loops through safe panel
chains. If pause verification says another visible panel must be cleared first,
the runner reclassifies, runs the same terminal-outcome audit, clears the next
safe panel, and tries to pause again. Island-complete/shop screens still go
through the conservative shop/leave handler instead of blind leave clicks.

Focused regression:
- `python3 -m pytest tests/test_lightning_runner.py -q -k "paused_segment_panel or post_segment_panel"`

## 2026-06-07 - Intro Panels, Route Commit, And Deployment Classifier Recovery

Hypothesis: the reliable baseline should trust concrete bridge mission state
over low-confidence UI labels, while still requiring exact preview proof before
one-way mission commits.

Segments: baseline autonomous wrapper attempts `20260607_002748_218`,
`20260607_002951_831`, and `20260607_003240_955`.

Evidence:
- Active island intro CEO dialogue can score higher as `perfect_island_panel`.
  The visible-control chooser now routes active intro dialogue to
  `bottom_continue`, while real overlay perfect-island panels keep
  `panel_continue`.
- Baseline unassigned multi-region previews can hide Start Mission behind CEO
  dialogue. After dismissing dialogue, route start may now commit by repeating
  the same verified red-region coordinate only when `cmd_recommend_mission`
  still reports the same `bridge_preview` mission id. The broad preview-board
  fallback remains forbidden for this case.
- A route start reached `Mission_Volatile` with `in_active_mission=true`,
  `phase=unknown`, `turn=0`, `deployment_zone_count=12`, and `mech_count=0`,
  but CV labeled the screen `island_map`. If no save-backed route candidates are
  available and the bridge has a concrete active `mission_id`, `lightning_attempt`
  now proceeds through the normal `deploy_recommended` + CONFIRM path.
- Segment auto-route handoffs now pass `allow_pause_map_peek=False` into
  `lightning_route_start`; the selected candidate already came from the paused
  route-plan step, and the opened preview is still validated with a fresh
  `bridge_preview` read before Start.
- Segment auto-route handoffs also carry the candidate `window_x/window_y` into
  `lightning_route_start`. Disabling the redundant map peek is only safe when
  the verified visual coordinate travels with the visual index; when coordinates
  are present the segment omits the index from the command call to avoid an
  ambiguous route-start input.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_start or deploys_active_unknown_phase or does_not_deploy_from_visible_island_map"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "route_gate or route_auto_start or deployment_bridge_state_uncertain or paused_segment_panel"`

## 2026-06-07 - Route Retry Proof And Stale Deployment Confirm Gate

Hypothesis: route retries chosen from live visual probes must keep using preview
proof, and UI-fallback deployment must prove that Confirm reached live bridge
combat before the segment is allowed to retry.

Evidence:
- A Detritus route probe correctly vetoed the first unlabeled visible region,
  but the retry loop re-entered the top route-start branch and recomputed
  `verify_route=True` from the missing mission id. Segment state now carries an
  explicit route-start verification flag; auto-probe candidates and retries keep
  `verify_route=False`, pass exact window coordinates, and rely on the opened
  live preview for mission proof.
- An R.S.T. attempt reached `Mission_Filler` deployment with stale bridge
  heartbeat. `deploy_recommended` timed out and used UI fallback, Confirm was
  clicked, but the next combat loop still saw `phase=unknown`, no active mechs,
  and the stale deployment zone. The attempt now waits after a warning-level UI
  fallback Confirm for a live combat/deployment transition. If the bridge never
  proves live, it returns `deployment_bridge_state_uncertain` with
  `deploy_confirm_bridge_not_live` evidence before entering combat, letting the
  autonomous wrapper abandon/restart instead of redeploying from stale data.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "ui_fallback_deploy_when_confirm_never_goes_live or retries_after_vetoed_probe_preview or stops_after_exhausting_unassigned_multi_region_previews"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "stale_deploy_confirm_bridge_gate or stale_map_deployment_bridge_gate or deployment_bridge_state_uncertain"`

## 2026-06-07 - Stale Bridge Preview Blocks Before Route Commit

Hypothesis: a route-start preview is only safe commit evidence when the bridge
preview payload itself is fresh. A stale bridge `mission_id` must not authorize
Start Mission, even if the route click used exact coordinates.

Evidence:
- Autonomous attempts `20260607_010944_884`, `20260607_012815_481`, and related
  rerolls proved that route auto-start could validate a stale
  `bridge_preview` mission id, click Start Mission, then recover only after the
  loaded mission differed (`Mission_Survive` -> `Mission_Dam`, `Mission_Belt`
  -> `Mission_Acid`). Recovery was safe, but too late for reliability.
- `cmd_recommend_mission` now annotates synthesized `bridge_preview` routes with
  heartbeat/state freshness (`bridge_preview_live`, `bridge_state_age_seconds`,
  and related fields). `lightning_route_start` treats stale preview proof as a
  pre-Start route gate and pauses instead of clicking Start.
- Baseline auto-start now keeps the broad preview-board click out of the guarded
  commit path. It may commit with visible Start Mission, or after dialogue
  dismissal with a revalidated region-repeat, but not through an unscoped board
  click.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q -k "route_auto_start or stale_bridge_preview or baseline_blocks_board_fallback or adapts_stale_preview_reason or preview_mismatch or route_mission_mismatch or route_gate or deployment_bridge_state_uncertain or stale_deploy_confirm_bridge_gate"`

## 2026-06-07 - Guard Route Preview From Committing Vetoed Missions

Hypothesis: a route preview click can be state-changing if the paused map has
already selected or half-opened a mission preview. Baseline route-start must
prove the unpaused screen is still a plain island map before clicking a region,
and must treat turn-zero deployment after a preview click as a committed route
mismatch rather than a retryable preview-only block.

Evidence:
- Autonomous run `lightning_20260607_031606_512` repeatedly reported
  `route_preview_auto_start_vetoed_before_start`, but the live bridge was
  already in turn-zero deployment for vetoed missions such as `Mission_Volatile`
  and `Mission_Dam`.
- Attempts `20260607_032311_920`, `20260607_032600_915`,
  `20260607_032828_266`, `20260607_033033_271`, and `20260607_033238_569`
  showed the same preview/commit spill. The clearest artifact was
  `recordings/20260607_033033_271/lightning_route_mismatch.json`, with expected
  `Mission_Mines`, actual `Mission_Volatile`, `phase=combat_enemy`, and
  `turn=0`.
- Because the old preview-only label was retryable, the wrapper could abandon
  and reroll after the mismatch, but it wasted attempts and sometimes left the
  final blocked attempt sitting in an active route state.

Result: guarded baseline route previews now split the pause-resume action from
the region click. When real window evidence is available, route-start resumes,
checks bridge/UI state, and blocks before the region click if the unpaused state
is an existing preview, deployment, active turn-zero mission, or anything other
than an island map. If the region click still reaches turn-zero deployment,
route-start writes a route-mismatch artifact and runs the deployment-abandon
recovery before returning `route_mission_mismatch_after_start[_recovered]`.
The autonomous wrapper treats the pre-click active-mission guard as a
recoverable precombat route gate only when the segment contains turn-zero
deployment evidence with no active mechs, then abandons/restarts from verified
setup while attempts remain.

Follow-up evidence:
- Live run `20260607_035107_784` proved the new guard blocked before another
  region click when the bridge already showed stale turn-zero `Mission_Mines`
  deployment (`phase=unknown`, `active_mechs=0`, `deployment_zone_count=12`).
  The wrapper initially repeated the guard because the new reason was outside
  the recoverable route-gate token set.
- Follow-up attempts `20260607_040332_805` and `20260607_040557_903` proved the
  wrapper could safely abandon/restart from the new guard, but also showed that
  the same pre-click active-mission handoff can load a route-policy-safe mission
  such as `Mission_Artillery`. Abandoning those safe handoffs burns attempts
  without increasing baseline reliability.
- Live attempt `20260607_041806_961` proved the veto side of the policy: the
  handoff exposed `Mission_Tanks`, wrote
  `recordings/20260607_041806_961/lightning_route_mismatch.json`, and recovered
  without deployment. The outer runner initially stopped because the active
  guard reason was nested in the recovered mismatch artifact rather than on the
  direct route-start step.
- Live attempt `20260607_042336_041` exposed the stale-map side: the bridge
  reported turn-zero `Mission_Tides`, but repeated screenshots showed the
  Archive island map with two red regions still visible. Treating that as a
  playable handoff wedged `lightning_segment` inside the next attempt wait.
- Follow-up autonomous validation from the title screen proved the stale-map
  block was safe but too wasteful. Attempts `20260607_043957_132`,
  `20260607_044500_628`, and `20260607_044729_668` each reached a visible
  corporate island map, built save-backed route candidates, then hit
  `visible_island_map_with_stale_deployment_bridge` because the old
  `/tmp/itb_state.json` still described turn-zero deployment for missions such
  as `Mission_Train`, `Mission_Dam`, or `Mission_Dam` while the bridge
  heartbeat was stale. The wrapper abandoned/restarted correctly, but the cycle
  could burn all attempts without entering combat.

Follow-up result: the guarded route-start helper now returns an explicit
`ACTIVE_MISSION` handoff when pause-resume reveals turn-zero deployment before a
region click. `cmd_lightning_route_start` validates that bridge mission against
the active route policy. Policy-safe missions return
`route_preview_active_mission_before_region_click_playable` and let
`lightning_segment` continue to deployment/combat with the actual mission.
Missing or vetoed missions still write mismatch evidence and use the
route-mismatch recovery path before returning
`route_mission_mismatch_after_start[_recovered]`. The autonomous wrapper now
treats that recovered mismatch artifact as rerollable only when the nested
block itself proves the active handoff reason plus turn-zero deployment with no
active or deployed mechs. If the bridge reports a route-policy-safe active
mission but CV still sees the island map, route-start returns
`visible_island_map_with_stale_deployment_bridge` instead of continuing to
deployment; the wrapper may reroll that stale-map gate while attempts remain.
The later cleanup fix makes visible-map routing authoritative before the route
command is emitted: when `lightning_attempt` returns save-backed route
candidates from a visible island map while bridge state is absent or stale, it
removes stale state/cmd/ack bridge files and records `stale_bridge_cleanup`.
The guarded route-preview path also clears stale bridge files and proceeds with
the region click when CV sees a map and the bridge reports turn-zero deployment
with a stale heartbeat. Fresh/live turn-zero deployment still uses the active
mission handoff or mismatch-recovery paths.
Subsequent live validation showed one more retry hazard: after a live preview
probe vetoed a candidate with no save-backed mission id, the next candidate
could be attempted while the first mission preview was still open behind pause.
The guard now allows that retry only through the calibrated
`dialogue_then_region_repeat` suffix, dropping the raw first point click and
dismissing the advisor dialogue before reselecting the next region. Existing
preview states without that suffix still block before any region click.
Live baseline attempt `20260607_084545_921` then proved the route probe could
open a clearly visible Archive `Mission_Satellite` preview (`Excavation Site`,
`Defend the Satellite Launches`) while the bridge remained unavailable/stale.
Because visible preview OCR only recognized Tanks, the auto-start block
collapsed to `missing_route_mission_id`, retried another unlabeled candidate,
then abandoned/restarted after both probes looked unidentifiable to the runner.
The OCR table now recognizes mission-specific preview phrases for Satellite and
other common objective missions. OCR remains veto-only for speed routing, but
baseline routing may treat recognized, non-vetoed mission text as Start
authority only after the normal visible Start Mission and post-start mission-id
verification paths pass. Recognized vetoed OCR previews now report concrete
route policy reasons such as `baseline_vetoed_mission:Mission_Satellite`
instead of `missing_route_mission_id`.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_start_blocks_existing_preview or recovers_preview_click_that_committed or route_start_blocks_vetoed_unlabeled or route_start_blocks_visible_ocr_vetoed"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_preview or route_start or route_mission_mismatch or auto_start"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "active_mission_before_route_region_click or stale_map_deployment_bridge_gate or stale_deploy_confirm_bridge_gate"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "route_gate or route_mission_mismatch or route_auto_start or deployment_bridge_state_uncertain or stale_deploy_confirm_bridge_gate or active_mission_before_route_region_click"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "safe_active_mission_before_probe or vetoed_active_mission_before_probe or route_start_blocks_existing_preview or recovers_preview_click_that_committed"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_preview or route_start or route_mission_mismatch or auto_start"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "safe_active_mission_before_probe or visible_map or stale_map_active_handoff"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_preview or route_start or route_mission_mismatch or auto_start or stale_map_active_handoff"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "recovered_active_mission_mismatch or active_mission_before_route_region_click or route_gate or route_mission_mismatch"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "stale_map_active_route_handoff or stale_map_deployment_bridge_gate or recovered_active_mission_mismatch"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "stale_active_map_bridge or ambiguous_visible_map_when_bridge_missing or ambiguous_map_over_stale_deployment or visible_map_over_stale_active_combat or safe_active_mission_when_visible_map"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "route_preview or route_start or route_mission_mismatch or auto_start or stale_map_active_handoff or stale_active_map_bridge"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "existing_preview or reselects_from_existing_preview or retries_after_vetoed_probe_preview or route_preview or route_start"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "preview_only_route_gate or route_gate or stale_map_active_route_handoff or stale_map_deployment_bridge_gate or recovered_active_mission_mismatch"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "visible_preview_ocr or visible_ocr or auto_start or route_start"`
- `python3 -m pytest tests/test_lightning_runner.py -q`
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py -q`

## 2026-06-07: Expected-ID OCR Route Start And Pause-Guard Conflict

Observation: an expired Blitzkrieg/R.S.T. timeline at `0:32:42` was paused on
the corporate map with two visible red regions (`Storage Vaults` /
`Mission_Artillery` selected at window `(698, 356)`). The bridge no longer
emitted `island_map`, so `lightning_route_start --visual-region-index 0
--expected-mission-id Mission_Artillery --route-routing lightning_baseline`
could click the visible region but blocked at
`route_preview_mission_unverified_before_start` even though the live preview OCR
recognized `Defend the Artillery Support`.

Result: baseline route-start now accepts matching visible-preview OCR when an
explicit expected mission id is supplied. The live proof wrote OCR evidence at
`/var/folders/pr/cvsvvtw50yl01vnrqb4jnxfr0000gn/T/itb_lightning_preview_ocr_24154.png`,
authorized `Mission_Artillery`, clicked `mission_preview_board`, and the fresh
post-start bridge snapshot reported turn-zero `Mission_Artillery` deployment.
Speed routing remains OCR-veto-only, and contradictory OCR still blocks before
Start.

Follow-up: the deployment-only parking segment used `--max-turns 0`, placed all
three mechs, then left the live bridge in combat. A second segment refused to
act because the save/profile timer was already over 30 minutes, and the pause
guard initially trusted a visual `title_screen` false positive even though the
fresh bridge said `combat_player`. The pause guard now lets fresh active-combat
bridge evidence override `title_screen` / setup false positives and clicks
Pause; stale combat snapshots can still be overridden by real setup screens.

Focused regressions:
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "expected_id_accepts_matching_baseline_ocr or pause_guard_pauses_title_false_positive or compact_region_point or region_repeat"`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "lightning_attempt"`
- `python3 -m pytest tests/test_lightning_war_tools.py tests/test_lightning_runner.py tests/test_lightning_autonomous_conductor.py -q`

## 2026-06-07: Tides Reallowed, Dam/Disposal Vetoed, Prior-Melee Audit Fix

Live baseline command:
`python3 game_loop.py lightning_autonomous --mode baseline --target-islands 2
--max-attempts 20`.

Follow-up attempts showed that a blanket baseline Tides veto exhausted route
attempts too easily after Dam/Disposal became real safety blocks. Current
baseline policy allows reliable speed-slow missions such as `Mission_Tides`,
`Mission_Mines`, `Mission_Cataclysm`, and `Mission_Artillery`, while vetoing
`Mission_Dam`, `Mission_Disposal`, Train, Satellite, Tanks, Bad Repairs, fragile
ally/counter objectives, and similar surprise-prone missions.

Live run `20260607_210306_865` started Pinnacle `Mission_Tides`, solved and
executed turn 1, then turn 2 stopped with `THREAT_AUDIT_BLOCKED`: Scorpion
uid `23719` at D4 still visibly targeted E4 after all mech actions. Replay of
the exact stored `m00_turn_02_solve_input.json` showed the Rust prediction was
sound: lower-UID Scorpion uid `23716` attacks D4 first and kills the 1 HP D4
Scorpion before E4 can be hit. The false block was in the Python threat audit,
which credited earlier projectiles, artillery, Bouncer bumps, and pushes, but
not direct melee friendly fire.

Result: `src.solver.threat_audit` now returns
`attacker_will_die_to_prior_melee` when a lower-UID queued melee attacker will
kill the still-threatening attacker before its turn. The live run remains
parked pre-End-Turn until this fix is tested and the held click is deliberately
resumed from fresh evidence.

Focused regressions:
- `python3 -m pytest tests/test_threat_audit.py -q`
- `python3 -m pytest tests/test_lightning_war_tools.py -q -k "baseline_route_status"`
- `python3 -m pytest tests/test_lightning_runner.py -q -k "stop_token_evidence"`
