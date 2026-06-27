# Lightning War Loop Log

## 2026-06-21 Route-Probe Cache And Volatile Timeout Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Previous setup proof was
  `screenshots/075_new_game_setup_after_164203_pinnacle_pending_cleanup.png`.
- Route preview churn was the leading blocker after Airstrike/Solar vetoes and
  unverified previews consumed the first-mission gate.
- Live speed burst ran attempts `20260621_171025_868`,
  `20260621_171622_387`, and `20260621_172222_055`.
- Archive attempt 1 started at screenshot/OCR `0:01:09`; both route probes
  failed as `route_preview_not_opened_before_start`.
- R.S.T. attempt 2 started at screenshot/OCR `0:00:58`; both route probes
  opened unrecognized previews (`no_known_preview_text_match`), then reset.
- Archive attempt 3 started at screenshot/OCR `0:01:01`; candidate 1 opened
  Excavation Site / Volatile Vek text, but the helper stopped with
  `route_start_subcall_timeout`.
- Final durable proof:
  `screenshots/076_after_172222_route_start_timeout_pause_0222.png`
  (`Oh 2m 225` -> `0:02:22`).

Action taken:

- Added route-probe cache support in the runner/session/segment path.
- Changed speed-mode first-island retry order to Archive/R.S.T./Archive.
- Added focused tests for route-probe cache round trip, soft preview retries,
  cached failed labeled probes, and speed-mode island cycling.
- Ran one guarded speed burst and stopped on the timeout without clicking an
  unverified Start Mission.

Verification:

- `python3 -m py_compile src/loop/commands.py src/loop/lightning_runner.py src/loop/session.py tests/test_lightning_war_tools.py tests/test_lightning_runner.py`
  passed.
- Focused route-probe/cache pytest selected 7 tests and all passed.
- Focused runner route/island tests selected 8 tests and all passed.
- Touched-file `git diff --check` passed.

Decision:

- Do not continue the paused branch or click Start Mission from timer headroom.
- Patch route-start so opened Volatile/unknown previews return a fast
  structured veto/block instead of timing out, then reset to setup before the
  next live speed burst.

Memory compressor:

- Rule to keep: route-probe cache can select/skips probes only; it is never
  Start Mission authority.
- Mistake to avoid: treating opened Volatile preview text as a reason to wait
  out the subcall or force Start Mission.
- Faster decision procedure: if preview OCR sees `Do not kill the Volatile Vek`
  or `Protect the Power Generator`, classify/veto quickly.
- HEURISTICS line: Volatile preview timeout is tooling debt, not a live-route
  opportunity.

## 2026-06-21 First-Island False-Panel Fix And Route-Veto Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Previous speed burst had stopped on first-island selection uncertainty after
  route gates, while screenshot evidence showed no red mission regions. This
  was too early to treat as a route map but safe as an unreadable first-island
  picker fallback.
- The latest live burst created recordings `20260621_155921_400`,
  `20260621_160446_183`, and cleanup branch `20260621_160937_729`.
- Archive reached first-island pause with visible timer `0:00:58`; R.S.T.
  reached first-island pause with visible timer `0:00:51`.
- Route preview OCR then vetoed `Mission_Airstrike` on Archive, and
  `Mission_Solar` plus `Mission_Airstrike` on R.S.T. No Start Mission was
  clicked.
- Final cleanup branch stopped on Pinnacle
  `first_island_selection_pending_unverified`; pause proof is
  `screenshots/073_after_160937_pinnacle_pending_pause_0049.png`, reset proof
  is `screenshots/071_new_game_setup_after_160937_pinnacle_pending_reset.png`,
  and Airstrike preview proof is
  `screenshots/072_route_veto_airstrike_preview_0141.png`.

Action taken:

- Added a narrow unreadable first-island corp-panel fallback that only fires
  when no red mission regions are visible; readable wrong-corp panels still
  block.
- Added focused regression coverage for the false-panel first-island picker
  case.
- Ran a guarded speed burst and then abandoned the final dead branch safely back
  to setup.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused first-island picker pytest selected 9 tests and all passed.
- Focused route/OCR pytest selected 11 tests and all passed.
- Runner carry-over pytest selected 1 test and passed.
- `git diff --check -- src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.

Decision:

- First-island false-panel handling is no longer the next bottleneck.
- The next loop should prune/cache route-preview candidates so Solar,
  Airstrike, and unknown previews do not consume the first-mission segment
  budget.

Memory compressor:

- Rule to keep: unreadable first-island corp-panel evidence can fall back to
  zero-red map evidence; route maps still need mission OCR authority before
  Start Mission.
- Mistake to avoid: broadening first-island fallback into route-start
  authority.
- Faster decision procedure: if a branch hits repeated Solar/Airstrike vetoes
  before mission start, preserve proof and patch candidate ordering/caching
  before another speed burst.
- HEURISTICS line: veto proof is safe but expensive; skip known bad route
  candidates before spending another full preview/OCR cycle.

## 2026-06-21 OCR Label Route-Click Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- R.S.T. branch proof `screenshots/063_after_144855_visual_index_gate_pause_0156.png`
  showed a dead precombat route branch around OCR `0:01:56` after a
  visual-index retry handoff lost usable click coordinates.
- Setup proof after reset:
  `screenshots/064_new_game_setup_after_visual_index_gate_reset.png`.
- Speed run `recordings/20260621_150049_520` reached Archive route-ready at
  OCR `0:00:54`, then blocked as `route_preview_not_opened_before_start`.
- The Archive telemetry identified `Accord Repository` with OCR label target
  `(973,443)` and visual centroid `(976,416)`; the centroid probe did not open
  the preview. Durable proof is
  `screenshots/065_after_150049_archive_preview_not_opened_0139.png`.

Action taken:

- Patched pending visual-index route retries to carry `window_x/window_y`.
- Patched OCR-labelled auto-route probes to use OCR label coordinates while
  preserving visual-index behavior for generic distinct-label probes.
- Added focused regressions for coordinate carry and OCR-label click-target
  selection.
- Abandoned the dead Archive branch after the patch and captured setup proof:
  `screenshots/066_new_game_setup_after_archive_preview_not_opened_reset.png`.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route-start pytest selected 6 tests and all passed.
- Runner carry-over pytest selected 1 test and passed.
- `git diff --check -- src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.

Decision:

- Next live proof should run from verified setup and test whether OCR-label
  route clicks open the preview cleanly before the first-mission `0:03:00` gate.

## 2026-06-21 Detritus Start-Leak Guard Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Speed run `20260621_124307_841` reached Archive route labels `Martial
  District` and `Central Museums`, then correctly stopped on
  `multi_region_live_preview_probe_without_route_identity`.
- Restart from setup tried next first island R.S.T. but final proof showed
  Detritus Disposal selected at visible timer `0:00:03`:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/050_restart_failure_detritus_panel_0003.png`.
- The wrong Detritus branch was cleared and abandoned back to setup:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/051_after_detritus_restart_reset_to_setup.png`.

Action taken:

- Shortened `setup_modal_start` hold time to avoid carrying the Start click
  into the first-island picker.
- Added selected-corporation OCR identity proof for first-island corp panels.
- Blocked `cmd_lightning_start_run` when a preselected corp panel does not
  match the requested first island.
- Preserved `first_island_selected_mismatch` through the autonomous runner.
- Verified py_compile plus focused Lightning start and runner tests.

Decision:

- Keep `multi_region_live_preview_probe_without_route_identity` hard-blocking.
- Next live action is a fresh speed burst from setup with the new wrong-island
  guard active.

## 2026-06-21 Recorded-Island Recovery Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Screenshot `042_after_pinnacle_route_no_candidates_0135.png` was not a
  route map; it was the four-corporation picker with Pinnacle highlighted.
- After recorded-island recovery, the branch reached real route labels:
  `Pinnacle Garden`, `Cryogenic Labs`, and `Thermal Dampeners`.
- Durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/043_after_pinnacle_route_ready_multi_region_0246.png`
  shows the route-ready state around `0:02:46`.
- Reset proof is
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/044_new_game_setup_after_pinnacle_route_reset.png`.

Action taken:

- Patched the route gate to emit
  `recorded_first_island_selection_map_requires_confirm` when only
  `current_island` is recorded and picker evidence remains.
- Extended `lightning_select_first_island` to recover that recorded-first-island
  state from pause.
- Patched first-island picker evidence to ignore pause overlays.
- Verified focused route/selection tests (`17 passed`) and py_compile.
- Live-tested the recovery, reached route labels, then reset because the labels
  lacked mission identity near the segment gate.

Decision:

- Do not Start Mission from unlabeled multi-region route labels.
- Next live action is a fresh speed burst from setup.

Memory compressor:

- Rule to keep: recorded `current_island` plus picker proof means confirm the
  same island, not route.
- Mistake to avoid: treating pause-overlay OCR/screenshots as first-island
  picker evidence.
- Faster decision procedure: if route labels are still unassigned near
  `0:03:00`, reset instead of preview probing.
- Thing to test next: whether a fresh attempt reaches a single safe route or an
  allowlisted OCR preview before `0:03:00`.
- HEURISTICS line: real route labels without mission identity are not Start
  Mission authority.

## 2026-06-21 Selected-Island Route Guard Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Clean speed validation reached `first_island_paused` on Archive, R.S.T., and
  Pinnacle after the Archive click coordinate was calibrated.
- Current active run is `20260621_114330_394`, paused on Pinnacle, no mission
  started.
- Durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/042_after_pinnacle_route_no_candidates_0135.png`
  shows visible timer around `0:01:34-0:01:35`.
- The latest guarded resume stopped at `route_auto_start_not_allowed`; the
  attempt reason was `bridge_snapshot_unavailable_visible_island_map`, with no
  route candidate.

Action taken:

- Patched the route-visible-map caller so first-island picker evidence still
  blocks before selection, but is suppressed once selected-island session context
  exists.
- Added `_lightning_session_has_selected_island_context` and focused tests for
  blank-session vs recorded-session behavior.
- Verified with focused route/selection pytest (`13 passed`) and py_compile.
- Took one guarded live resume to validate the false
  `first_island_selection_map_without_route_context` stop was gone.
- Re-paused with `lightning_ui ensure_pause --include-ocr` and preserved durable
  proof with `lightning_peek after_pinnacle_route_no_candidates_0135 --include-ocr`.

Decision:

- Do not force Start Mission from the current zero-candidate selected-island map.
- Next loop should patch selected-island route extraction against screenshot
  `042_after_pinnacle_route_no_candidates_0135.png`, then take one guarded
  resume only if route proof is safe.

Memory compressor:

- Rule to keep: selected-island context suppresses the first-island zero-red
  guard; pre-selection picker proof still wins.
- Mistake to avoid: treating timer headroom as route authority.
- Faster decision procedure: after no-bridge route stops, immediately pause,
  preserve proof, then patch extraction offline.
- Thing to test next: whether selected-island map screenshots can produce safe
  route candidates without stale bridge/save route identity.
- HEURISTICS line: after `current_island` is recorded, zero-red
  `island_map_or_unknown` is not enough to call the first-island picker.

## 2026-06-21 Route-Context Guard Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before visible Timeline Playtime reaches `0:30:00`, with each
mission segment at or under `0:03:00`.

Evidence reviewed:

- Speed runner attempts reached route gates but no mission start.
- Durable OCR proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/040_after_speed_attempt3_first_island_context_block_0104.png`
  showed the dead branch around `0:01:05`, with no island progress.
- The runner output showed the key blocker:
  `first_island_selection_map_without_route_context`.

Action taken:

- Preserved timer/UI proof with `lightning_peek --include-ocr`.
- Abandoned the dead branch back to `new_game_setup`.
- Patched `cmd_lightning_attempt` so first-island selection evidence is checked
  before visible-map route candidates are accepted.
- Patched route-map screening so labeled plain maps are not falsely blocked as
  `route_preview_card_visible`.
- Added/updated focused tests for the route guard and current save-route scorer.

Decision:

- Do not click Start Mission from an unassigned route candidate or
  four-corporation picker.
- Next live action is a fresh speed burst from setup.

Memory compressor:

- Rule to keep: first-island picker evidence beats route candidates.
- Mistake to avoid: treating stale/save-backed route candidates as route-ready
  when the visible map has zero mission regions.
- Faster decision procedure: preserve OCR proof, reset dead precombat branches,
  then patch the earliest false-ready gate.
- Thing to test next: whether the next speed burst advances past first-island
  route selection into a verified mission start.
- HEURISTICS line: first-island picker proof beats route candidates.

## 2026-06-20 Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- Current `run_notes/lightning_war_smoke_2026-06-20/notes.md` includes repeated
  route preview/block records, including `route_preview_block` and
  `current_after_route_block`.
- `run_notes/lightning_war_conductor_2026-06-20.jsonl` shows setup passed,
  Archive/start handoff ran, pause was verified, and the segment stopped at
  `mission_preview_requires_route_validation`.
- Latest inspected screenshot shows pause menu, Easy/Base Content, Blitzkrieg,
  and timer `0h 0m 05s`.

Action taken:

- Spawned two read-only analysis agents for current-state extraction and
  route/timing critique.
- Created durable artifacts: `GOAL.md`, `STATE.md`, `STRATEGY.md`,
  `HEURISTICS.md`, `EVAL.md`, `BLOCKERS.md`, and `NEXT.md`.
- Copied the current pause/timer screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/050_current_pause_timer_0m05.png`.
- Folded the route critique into the strategy: conservative baseline, first
  proven low-friction mission, and route/start reliability before combat speed.
- Did not directly control the game.

Decision:

- Do not click Start Mission from the hidden/uncertain preview.
- Highest-leverage next move is a manual reveal/classify/re-pause step so the
  route candidate can be proved before committing the first mission.

Memory compressor:

- Rule to keep: screenshots are the timer authority.
- Mistake to avoid: clicking Start Mission from
  `mission_preview_requires_route_validation`.
- Faster decision procedure: take the first proven baseline-safe low-friction
  mission instead of browsing previews live.
- Thing to test next: whether the reveal is a safe preview, a veto preview, or
  deployment.
- HEURISTICS line: do not spend live timer shopping for a perfect first mission.

## 2026-06-20 Loop 2

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- Durable artifacts still pointed at the earlier route gate and `0:00:05`
  paused screenshot.
- No newer run-note screenshot existed after
  `050_current_pause_timer_0m05.png`.
- A standalone read-only `lightning_ui classify --include-ocr` returned
  `visible_ui: new_game_setup`.
- The classifier screenshot showed Blitzkrieg on the new-run setup screen with
  Bethany Jones, not a paused mission preview.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/051_current_new_game_setup.png`.
- Updated `STATE.md`, `STRATEGY.md`, `BLOCKERS.md`, and `NEXT.md` so the next
  action no longer follows the stale route-preview reveal instruction.
- Did not click or otherwise control the game.

Decision:

- Treat the route-gate state as historical. Current work returns to setup proof.
- Highest-leverage next move is to open the setup Difficulty modal manually,
  verify Easy/Base Content, then start the fresh timeline only after proof.

Memory compressor:

- Rule to keep: fresh screenshot/classifier evidence invalidates stale route
  instructions.
- Mistake to avoid: following a preserved `NEXT.md` action after the visible
  screen has changed.
- Faster decision procedure: classify current screen before giving a live manual
  click when the last action may have been executed out of band.
- Thing to test next: whether the setup modal is Easy/Base Content/AE off.
- HEURISTICS line: before acting on a saved next action, verify the current
  visible UI still matches its precondition.

## 2026-06-20 Loop 3

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- `STATE.md` and `NEXT.md` expected the user to open the Difficulty Setup modal.
- No newer run-note screenshot existed beyond loop 2 setup proof.
- A standalone read-only `lightning_ui classify --include-ocr` again returned
  `visible_ui: new_game_setup`.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/052_current_new_game_setup_still_waiting.png`.
- Updated `STATE.md`, `NEXT.md`, `BLOCKERS.md`, and `EVAL.md` to record that
  the setup modal is still not open and to clarify the one-click manual action.
- Did not click or otherwise control the game.

Decision:

- Current blocker is pre-modal setup proof, not route proof or combat.
- Highest-leverage next move remains one manual click on the large top-right
  setup `Start`, then stop before the modal's final `Start`.

Memory compressor:

- Rule to keep: the first setup `Start` opens the verification modal; the second
  setup `Start` begins the live timeline.
- Mistake to avoid: treating both Start buttons as equivalent.
- Faster decision procedure: if classifier still says `new_game_setup`, repeat
  exactly one instruction: open the setup modal and stop.
- Thing to test next: whether the modal verifies Easy/Base Content/AE off.
- HEURISTICS line: distinguish setup-open Start from final timeline Start.

## 2026-06-20 Loop 4

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- Durable artifacts expected the setup Difficulty modal to be opened.
- Latest run-note screenshot was still the pre-modal setup screen.
- A standalone read-only `lightning_ui classify --include-ocr` again returned
  `visible_ui: new_game_setup`.
- The classifier reported `new_game_setup_start` crop `[1790, 86, 2230, 246]`.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/053_current_new_game_setup_start_target.png`.
- Updated `STATE.md`, `NEXT.md`, `BLOCKERS.md`, and `EVAL.md` with the exact
  setup Start crop/center and the repeated pre-modal state.
- Did not click or otherwise control the game.

Decision:

- Current blocker remains pre-modal setup. Since the same manual action has
  persisted for three loops, actual run progress now requires the user click the
  setup Start once, or explicitly authorize direct control.
- Highest-leverage next move: click the visual center of the top-right setup
  `Start` button, currently around `(2010, 166)` in captured-window coordinates,
  then stop before the modal's final `Start`.

Memory compressor:

- Rule to keep: when a manual action repeats, include the visible target crop
  and center.
- Mistake to avoid: repeating a text-only instruction when a coordinate target
  can reduce ambiguity.
- Faster decision procedure: if `new_game_setup` persists, read the classifier
  crop for `new_game_setup_start` and give that as the manual target.
- Thing to test next: whether clicking that target opens the Difficulty Setup
  modal.
- HEURISTICS line: repeated manual UI instructions should include the detected
  control crop and center.

## 2026-06-20 Resumed Loop 1

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- `STATE.md` and `NEXT.md` still expected the setup Difficulty modal to be
  opened.
- A standalone read-only `lightning_ui classify --include-ocr` again returned
  `visible_ui: new_game_setup`.
- The classifier again reported `new_game_setup_start` crop
  `[1790, 86, 2230, 246]`.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/054_current_new_game_setup_still_target.png`.
- Created annotated manual-click proof at
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/054_current_new_game_setup_start_annotated.png`.
- Updated `STATE.md`, `NEXT.md`, and `EVAL.md` to reference the annotation.
- Did not click or otherwise control the game.

Decision:

- Current blocker remains pre-modal setup, but this resumed blocked audit is
  only at loop 1. Do not mark blocked again yet.
- Highest-leverage next move remains one manual click on the annotated
  top-right setup `Start`, then stop before the modal's final `Start`.

Memory compressor:

- Rule to keep: when text/coordinates fail to move a manual blocker, add an
  annotated screenshot.
- Mistake to avoid: marking resumed blocked state immediately after the first
  resumed loop.
- Faster decision procedure: if current UI is unchanged after a blocked resume,
  produce one stronger visual target artifact.
- Thing to test next: whether the annotated target opens the Difficulty Setup
  modal.
- HEURISTICS line: for repeated manual blockers, include an annotated screenshot
  target before declaring the resumed loop blocked.

## 2026-06-20 Resumed Loop 2

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- `STATE.md` and `NEXT.md` pointed to the annotated setup Start target.
- A standalone read-only `lightning_ui classify --include-ocr` again returned
  `visible_ui: new_game_setup`.
- The classifier still reported `new_game_setup_start` crop
  `[1790, 86, 2230, 246]`.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/055_current_new_game_setup_resumed_loop2.png`.
- Updated `STATE.md`, `BLOCKERS.md`, and `EVAL.md` to record resumed blocker
  count `2/3`.
- Did not click or otherwise control the game.

Decision:

- Current blocker remains pre-modal setup. This is resumed blocked-audit loop
  2 of 3 for the same manual setup-click condition.
- Highest-leverage next move remains one manual click on the annotated
  top-right setup `Start`, then stop before the modal's final `Start`.

Memory compressor:

- Rule to keep: after a blocked goal is resumed, count repeated same-state
  blockers from scratch.
- Mistake to avoid: marking blocked on resumed loop 2 instead of waiting for the
  third repeated resumed loop.
- Faster decision procedure: if current UI equals prior resumed blocker, update
  resumed count and do not re-explain old route evidence.
- Thing to test next: whether clicking the annotated target opens the Difficulty
  Setup modal.
- HEURISTICS line: resumed blocked audits need an explicit repeat count.

## 2026-06-20 Resumed Loop 3

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
ordinary mission under `0:03:00`.

Evidence reviewed:

- `STATE.md` showed resumed blocker count `2/3`.
- A standalone read-only `lightning_ui classify --include-ocr` again returned
  `visible_ui: new_game_setup`.
- The classifier still reported `new_game_setup_start` crop
  `[1790, 86, 2230, 246]`.

Action taken:

- Copied the fresh setup screenshot to
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/056_current_new_game_setup_resumed_loop3_blocked.png`.
- Updated `STATE.md`, `BLOCKERS.md`, `EVAL.md`, `LOG.md`, `NEXT.md`, and run
  notes to record resumed blocker count `3/3`.
- Did not click or otherwise control the game.

Decision:

- Current blocker remains pre-modal setup. This is resumed blocked-audit loop
  3 of 3 for the same manual setup-click condition.
- Actual run progress requires the user to click the annotated setup `Start`
  once, or explicitly authorize direct control.

Memory compressor:

- Rule to keep: after resumed count `3/3`, mark the goal blocked rather than
  repeating the same instruction.
- Mistake to avoid: leaving the goal active after the strict blocked threshold
  is met.
- Faster decision procedure: if resumed count reaches `3/3` and current UI is
  unchanged, update artifacts then mark blocked.
- Thing to test next: whether the annotated target opens the Difficulty Setup
  modal.
- HEURISTICS line: resumed blocker count `3/3` means set the goal blocked.

## 2026-06-20 Live Route-Start / Tooling Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- `lightning_preflight` passed non-timer blockers.
- The setup modal was verified Easy/Base Content after an autonomous recovery
  path briefly toggled Equipment Advanced Content on.
- `lightning_start_run --difficulty 0 --advanced-content off --first-island
  archive --no-segment` created run `20260620_180915_422` and paused on Archive
  with OCR timer around `0:00:59`.
- `057_current_after_route_block.png` proved the Archive map and timer around
  `0:00:59`; `058_after_mission1_route_ready.png` proved the map still visible
  at about `0:01:55`.
- Fresh `lightning_ui classify --include-ocr` after the route attempts proved a
  pause-menu timer around `0:03:27`, preserved at
  `run_notes/lightning_war_smoke_2026-06-20/screenshots/059_segment_pace_stop_0h03m27.png`.

Action taken:

- Stopped live play on the screenshot-proven segment-over-3:00 condition.
- Identified Remembrance Point as visual region index `0` and route-validated
  `Mission_Tides`, but the board/dialogue-board commit path did not transition
  into deployment.
- Updated Lightning route-start tooling so the default Lightning War commit mode
  is `visible-text`.
- Updated generated route candidate commands, autonomous runner/conductor
  defaults, CLI defaults, and the live runbook to prefer visible Start Mission
  text.
- Preserved baseline route behavior by rebuilding the actual baseline commit
  sequence after preview-only validation.
- Updated tests so visible-text success requires post-start deployment/combat
  proof.

Verification:

- Route harness passed: `99 passed, 338 deselected`.
- Runner/conductor route subset passed: `42 passed, 201 deselected`.
- Full `test_lightning_war_tools.py` was attempted but hit a pytest internal
  `WindowsPath` error on macOS, so it is not a clean signal.

Decision:

- Treat run `20260620_180915_422` as a pace-failed learning run.
- Restart fresh with visible-text route starts rather than continuing this
  timeline.

Memory compressor:

- Rule to keep: route preview validation is not a handoff; Start must produce
  fresh deployment/combat proof.
- Mistake to avoid: using broad board/dialogue-board route commits as the
  default under Lightning War timer pressure.
- Faster decision procedure: use `--route-start-mode visible-text` from the
  first route-ready command and stop on no-transition.
- Thing to test next: a fresh baseline autonomous run with visible-text defaults.
- HEURISTICS line: a visible Start Mission click with `NO_BRIDGE` or pause/menu
  still visible afterward is a failed transition until proven otherwise.

## 2026-06-20 Runner Dispatch / Restart / Intro Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- `074_peek.png` proved Archive map at `0:01:41` with Colonial Park and
  Retrospect Park both unassigned.
- `075_peek.png` proved R.S.T. Head Office dialogue at `0:00:49` after the
  runner dispatch fix restarted the old route gate.
- `076_peek.png` is the current proof: run `20260620_205629_683`, R.S.T. Head
  Office dialogue, visible timer `0:00:43`, paused again after capture.

Action taken:

- Rewired `game_loop.py lightning_autonomous` to use
  `src.loop.lightning_runner` instead of the older conductor.
- Added regression coverage for the CLI dispatch/defaults.
- Tightened pause OCR so active Head Office intro text with `MENU + CONTINUE`
  does not become a pause-menu false positive.
- Added intro-clearing paths before route planning and before stale
  deployment-shaped preview route validation.
- Ignored exact diagnostic
  `stale_bridge_preview_ignored_for_route_scoring` as a stop-token source so
  route gates can remain restartable.
- Ran three live speed passes. They restarted unassigned route maps safely but
  currently stop at paused R.S.T. intro route-validation shape.

Verification:

- `py_compile` passed for `game_loop.py`, `src/loop/commands.py`, and
  `src/loop/lightning_runner.py`.
- Runner focused tests passed: `5 passed, 224 deselected`.
- Lightning war tool focused tests passed: `4 passed, 447 deselected`.

Decision:

- Stop live play in a safe paused state. The next improvement is paused
  first-island intro handling, not combat tactics.

Memory compressor:

- Rule to keep: diagnostic ignored stale bridge preview is not a hard
  stale-bridge stop; it should not outrank route-gate restart evidence.
- Mistake to avoid: evaluating stale deployment bridge state while a paused HQ
  intro is the visible ground truth.
- Faster decision procedure: after first-island start, if pause peek reveals
  `Head Office` + `CONTINUE`, clear that safe dialogue before route validation.
- Thing to test next: paused first-island intro handoff from `cmd_lightning_start_run`
  into `lightning_autonomous`.
- HEURISTICS line: paused HQ intro is a UI panel, not route/deployment proof.

## 2026-06-20 Pause Overlay / Route Identity Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- `latest_lightning_speed_after_paused_intro_patch.log` proved the first
  post-pause clear ran but did not resume when the cheap classifier reported
  `mission_preview_panel` without attached OCR.
- `latest_lightning_speed_after_pause_ocr_tail_patch.log` still blocked at
  `mission_preview_requires_route_validation`; the cheap initial snapshot
  lacked OCR even though later pause snapshots had `Timeline Playtime`.
- `latest_lightning_speed_after_pause_score_tail_patch.log` proved the score
  overlay fix worked: the runner resumed from pause, got past the preview
  validation blocker, restarted, and reached a visible R.S.T. map route gate.
- `077_peek.png` is the current proof: run `20260620_213129_891`, paused on
  R.S.T. island map, visible timer about `0:02:24-0:02:25`.

Action taken:

- Added first-island post-pause tail clearing to both fresh start and pending
  first-island recovery helpers.
- Added pause recognition for pause-menu OCR and for strong pause-menu score
  plus heavy dark overlay.
- Preserved the active Head Office intro guard so visible `Head Office` +
  `CONTINUE` is not treated as pause.
- Ran three live speed passes and captured fresh timer/OCR proof after the
  final pass.

Verification:

- `py_compile` passed for `game_loop.py`, `src/loop/commands.py`, and
  `src/loop/lightning_runner.py`.
- Focused Lightning tools tests passed: `19 passed, 435 deselected`.

Decision:

- Stop live play in a safe paused route-map state. The next improvement is
  route identity assignment/probing for visible R.S.T. map regions, not combat
  tactics.

Memory compressor:

- Rule to keep: strong pause-menu score plus heavy dark overlay can prove pause
  before OCR is attached, but active intro text remains non-pause.
- Mistake to avoid: letting stale deployment bridge files supply route identity
  when the visible UI is an island map.
- Faster decision procedure: when the runner reaches visible map with unassigned
  route candidates, extract/attach visible labels or run a safe preview probe
  before Start Mission.
- Thing to test next: R.S.T. visible route identity assignment from OCR/map
  evidence with stale deployment bridge discarded.
- HEURISTICS line: visible island map proof outranks stale deployment bridge,
  but does not authorize Start Mission without route identity or preview proof.

## 2026-06-20 Route Label Probe / Click Target Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- `077_peek.png` and the clean map peek proved two visible R.S.T. route labels:
  `Lif eless Basin` and `Sub-Zero Range`.
- `latest_lightning_speed_after_route_label_patch.log` proved the route-label
  patch cleared `multi_region_live_preview_probe_without_route_identity` and
  selected candidate index `0`.
- The same live log proved the old centroid click `(604,386)` did not open a
  preview; the helper stopped at `route_preview_not_opened_before_start` before
  any Start Mission click.
- `078_peek.png` is the latest proof: paused map, visible timer `0:03:13`, no
  mission start. The current timeline is paced out.

Action taken:

- Attached map OCR labels from the clean map screenshot used for red-region
  extraction instead of from the pause overlay.
- Filtered pause-menu OCR labels out of region labels.
- Added exact `save_region_name` matching for visible labels when save route
  options exist.
- Allowed multiple Lightning War live-preview probes only when every candidate
  has a unique visible OCR label.
- Added an OCR-label-derived route click target below the label near mission
  objective icons; offline replay now targets `(586,403)` for `Lif eless Basin`
  and `(386,420)` for `Sub-Zero Range`.

Verification:

- `py_compile` passed for `game_loop.py` and `src/loop/commands.py`.
- Focused Lightning tools tests passed: `8 passed, 451 deselected`.
- Focused Lightning runner stop-token tests passed: `4 passed, 225 deselected`.

Decision:

- Stop live play. The current timeline is over the 3-minute pre-start budget,
  so the next attempt must restart/fresh-run and validate the new click target.

Memory compressor:

- Rule to keep: visible route labels may select a preview probe but never
  authorize Start Mission without preview/transition proof.
- Mistake to avoid: clicking the centroid of an irregular red route blob; it
  can leave the map unchanged.
- Faster decision procedure: if a labeled route click does not open preview,
  patch the click target toward the label/icon cluster before trying again.
- Thing to test next: fresh speed autonomous should use `(586,403)` for
  `Lif eless Basin`.
- HEURISTICS line: click below visible corp-map route labels near the mission
  icons, not at the red-blob centroid.

## 2026-06-20 R.S.T. Intro-Clear Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- `latest_lightning_speed_after_label_click_target.log` proved the
  label-derived `Lif eless Basin` click target `(586,403)` opened the preview.
- The same run abandoned the old paced-out timeline and started fresh run
  `20260620_220514_434`, reaching active `Mission_Lightning` with turn `0`,
  11 deployment zones, and `in_active_mission=true`.
- `079_peek.png` is the latest proof: paused over R.S.T. Head Office intro,
  visible top timer `1 0:02:08`, pause OCR `Oh 2m 085`.
- The blocker was not route identity. Active intro OCR showed
  `R.S.T. Corporation Head Office ... CONTINUE`, but color classification called
  it `island_map` with no safe control, so `clear_intro_panels` returned
  `NO_ACTION` and the runner later re-entered route/recommend logic.

Action taken:

- Extended the intro special case so proven `island_map` Head Office intro
  clears through `bottom_continue`; generic island maps remain protected.
- Extended `_lightning_intro_continue_likely_visible()` to include the
  `island_map` classifier case when intro text or active turn-0 deployment proof
  is present.
- Added a defensive `clear_tail_pause` guard: if `NO_ACTION` leaves an intro
  continue panel visible, return `BLOCKED / intro_continue_still_visible`.

Verification:

- `py_compile` passed for `game_loop.py` and `src/loop/commands.py`.
- Focused active-intro regression tests passed: `7 passed, 455 deselected`.

Decision:

- Stop live play. The current timeline is mission-started but still
  pre-deployment at about `0:02:08`; prefer a fresh/restarted speed attempt with
  the intro-clear patch.

Memory compressor:

- Rule to keep: active Head Office intro classified as `island_map` is safe to
  clear only through `bottom_continue` with intro proof.
- Mistake to avoid: treating `NO_ACTION/no_safe_panel_visible` as success while
  Head Office `CONTINUE` is still visible.
- Faster decision procedure: if the bridge says active turn-0 deployment and OCR
  says Head Office `CONTINUE`, clear the intro before route/recommend/deploy.
- Thing to test next: fresh speed autonomous should clear R.S.T. intro quickly
  and then deploy/enter combat or restart under timer proof.
- HEURISTICS line: no-op tail clear plus visible Head Office intro is a blocker,
  not a cleared tail.

## 2026-06-20 R.S.T. Route-Click Depth Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- Ran `python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3`.
- The runner cleared R.S.T. Head Office intro successfully:
  `intro_continue_cleared_without_bridge`.
- It then found three labeled R.S.T. regions (`Beautif ul Corner`, `Hardened
  Shale`, `Restricted Area`) with no save-backed mission ids.
- Route-start clicked `Beautif ul Corner` at `(942,423)` and stopped safely with
  `route_preview_not_opened_before_start`; no Start Mission click happened.
- Persistent proof `080_peek.png` shows the current timeline paused on the R.S.T.
  map at top timer `1 0:03:11`, pause OCR `Oh 3m Ils`, so the segment is over
  the `0:03:00` limit before deployment/combat.

Action taken:

- Raised label-derived route clicks from objective-icon depth to route-name
  depth: the vertical offset below OCR label bottom is now `+8` instead of
  `+28`.
- Added a `Beautif ul Corner` regression using latest-log OCR/region geometry.
- Updated existing `Lif eless Basin` expectation to the shallower target.

Verification:

- `py_compile` passed for `game_loop.py` and `src/loop/commands.py`.
- Focused route-label-depth/intro tests passed: `7 passed, 456 deselected`.

Decision:

- Stop live play. Current timeline is paced out by screenshot/OCR proof; next
  run should restart/fresh-attempt with shallower route-name clicks.

Memory compressor:

- Rule to keep: route labels can select a live preview probe, but click close to
  the label text, not down on objective icons.
- Mistake to avoid: treating route-preview click misses as mission proof or
  continuing a pre-deployment segment after visible timer exceeds `0:03:00`.
- Faster decision procedure: if a route-label-depth click still misses preview,
  patch to route-name center or reroll unassigned 3-region maps rather than
  spending more timer.
- Thing to test next: fresh speed autonomous should use `Beautif ul Corner`
  `(942,403)` or restart before timer leakage.
- HEURISTICS line: route-name OCR click targets should stay close to the visible
  route label; objective-icon clicks can fail to open preview.

## 2026-06-20 First-Mission Segment Gate Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
using screenshot/OCR timer proof only.

Evidence reviewed:

- Ran `python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3`.
- The runner did not restart the already paced-out current R.S.T. map. It
  route-probed `Beautif ul Corner` at `(942,403)` and again stopped safely with
  `route_preview_not_opened_before_start`.
- Persistent proof `081_peek.png` shows the current timeline paused on the R.S.T.
  map at top timer `1 0:04:03`, pause OCR `Oh 4m 025`/`Oh 4m 035`; the segment
  is over `0:03:00` before deployment/combat.

Action taken:

- Added `mission_segment_gate_seconds = 180` to the Lightning runner config.
- Added `_pace_gate()` logic for `first_mission_start_pace_gate`: speed mode now
  detects no islands complete, no recorded mission, `mission_index <= 0`, and
  visible/preflight timer at or over `0:03:00`.
- Added `_restart_after_initial_pace_gate_if_safe()` so available attempts
  abandon to setup and start the next first-island attempt instead of routing a
  dead timeline.

Verification:

- `py_compile` passed for `game_loop.py`, `src/loop/commands.py`, and
  `src/loop/lightning_runner.py`.
- Focused runner pace-gate tests passed: `4 passed, 227 deselected`.

Decision:

- Stop live play. Current timeline is paced out by screenshot/OCR proof; next
  run should prove the new first-mission start pace gate restarts before route
  planning.

Memory compressor:

- Rule to keep: visible/OCR `>0:03:00` before first mission progress means
  restart before route probing.
- Mistake to avoid: tuning route clicks on an already dead pre-deployment
  segment.
- Faster decision procedure: if speed mode begins from paused map with timer
  over `0:03:00`, first confirm abandon/restart, then inspect route behavior on
  the fresh slate.
- Thing to test next: speed autonomous should abandon `20260620_220514_434`
  before route planning and start attempt 2/3 from setup.
- HEURISTICS line: pre-mission timer over `0:03:00` is a restart gate, not a
  route-click tuning opportunity.

## 2026-06-21 Cataclysm Preview Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
mission segment under `0:03:00` by screenshot/OCR timer proof.

Evidence reviewed:

- `run_notes/lightning_war_smoke_2026-06-21/screenshots/010_peek.png` showed a
  paced-out paused branch around `0:02:02` after repeated route-start timeout.
- `run_notes/lightning_war_smoke_2026-06-21/screenshots/011_peek.png` is the
  latest proof: pause OCR `Oh 2m 295`, visible topbar `1 0:02:29`, and preview
  text for `Maglev Bunkers` with `CATACLYSM`.
- `latest_lightning_speed_after_dialogue_probe_preserve_patch.log` shows fresh
  run `20260621_022446_896`, first-route proof around `0:00:55`, then
  `route_start_subcall_timeout after 18.0s`, followed by
  `resume_from_pause_failed` after
  `mission_preview_dialogue_cleared_without_bridge`.

Action taken:

- Preserved `dialogue-region-repeat-preview-board` for unknown safe auto-start
  probes while keeping commit authority behind verified mission identity.
- Added visible-preview OCR patterns for `Mission_Cataclysm`: `cataclysm`,
  `cataclysmic`, and `fall into the depths`.
- Added `Mission_Cataclysm` to the Lightning War speed auto-start veto set.
- Added a focused regression test for Cataclysm visible-preview OCR.
- Verified syntax and focused Cataclysm/policy/route-start tests.

Decision:

- Do not salvage current branch; it is paused pre-start at about `0:02:29`.
- Next live action is the speed ladder. It should abandon/restart first, and a
  fresh Cataclysm preview should now produce
  `route_preview_auto_start_vetoed_before_start` instead of timing out.

Memory compressor:

- Rule to keep: timer truth is screenshot/OCR only.
- Mistake to avoid: treating an OCR vocabulary miss as a route-click failure.
- Faster decision procedure: when preview text exposes a known veto hazard,
  add that text to visible-preview OCR patterns and test the veto path before
  another live run.
- Thing to test next: fresh speed run after the Cataclysm OCR patch.
- HEURISTICS line: Cataclysm preview text should map to `Mission_Cataclysm` and
  speed-veto before Start Mission.

## 2026-06-21 Solar/Terraform Retry Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
mission segment under `0:03:00` by screenshot/OCR timer proof.

Evidence reviewed:

- Live speed run after the Cataclysm patch abandoned old run
  `20260621_022446_896` and started fresh run `20260621_024812_536`.
- The fresh run returned a structured pre-start veto for `Mission_Solar`:
  `route_preview_auto_start_vetoed_before_start`,
  `vetoed_mission:Mission_Solar`.
- Fresh proof `run_notes/lightning_war_smoke_2026-06-21/screenshots/012_peek.png`
  showed Solar Farms preview at topbar `1 0:01:27` and pause OCR around
  `Oh Im 285`.
- Resume with explicit `--route-visual-region-index 2` opened
  `Mission_Terraform` / `Detonation Bay` and stopped before Start Mission with
  `route_preview_mission_unverified_before_start`.
- Latest proof `run_notes/lightning_war_smoke_2026-06-21/screenshots/013_peek.png`
  shows pause OCR `Oh 2m 185`, topbar `1 0:02:19`, and Terraform preview text.

Action taken:

- Patched visible-OCR speed-veto handling so explicit retry indices also return
  `route_preview_auto_start_vetoed_before_start` when the preview mission is a
  speed veto.
- Added a regression for explicit retry index plus `Mission_Terraform` visible
  OCR returning `vetoed_mission:Mission_Terraform`.
- Verified syntax and focused Cataclysm/policy/route-start tests.

Decision:

- Do not salvage current branch; it is pre-start at about `0:02:19`.
- Next live action is the speed ladder again. It should abandon/restart first.

Memory compressor:

- Rule to keep: structured speed vetoes should apply to auto-start probes and
  explicit retry previews.
- Mistake to avoid: treating generic `route_preview_mission_unverified` as
  enough when visible OCR already identified a vetoed mission.
- Faster decision procedure: when a retry preview OCR matches a speed-vetoed
  mission, return the veto reason directly.
- Thing to test next: fresh speed run after explicit retry veto patch.
- HEURISTICS line: explicit retry visible-OCR speed vetoes need structured
  pre-start veto reporting.

## 2026-06-21 Hardin/Detonation Route-Gate Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands before the screenshot timer reaches `0:30:00`, with each
mission segment under `0:03:00` by screenshot/OCR timer proof.

Evidence reviewed:

- Speed run after the explicit-retry patch abandoned `20260621_024812_536` and
  started fresh run `20260621_030255_605`.
- Durable proof `screenshots/014_peek.png` showed a paused island map at about
  `0:01:13` with labels `Hardin Point`, `Corporate HQ`, and `Detonation Park`.
- Resume under gate attempted route-start at `Hardin Point` but stopped
  `route_start_click_failed` because the route-start screenshot subcall timed
  out after `18.0s`; durable proof `screenshots/015_peek.png` showed the same
  map at about `0:01:46`.
- Route-start floor was raised to `30.0s` and focused tests passed.
- Final resume stopped before another route click at
  `first_mission_route_start_pace_gate`; durable proof
  `screenshots/016_peek.png` shows pause OCR `Oh 2m 055/065`, topbar
  `1 0:02:05`, still on the island map.

Action taken:

- Raised `_LIGHTNING_ROUTE_START_MIN_SUBCALL_SECONDS` from `18.0` to `30.0`.
- Verified syntax and focused timeout/route-start tests.

Decision:

- Do not salvage current branch; it is over the conservative first-route gate.
- Next live action is the speed ladder again, expecting abandon/restart first.

Memory compressor:

- Rule to keep: timer truth is screenshot/OCR only.
- Mistake to avoid: diagnosing a slow screenshot timeout as a route click miss.
- Faster decision procedure: if route-start validation timeout is below the
  observed screenshot path, raise the envelope; if timer then exceeds the route
  gate, restart.
- Thing to test next: fresh speed run with 30s route-start floor.
- HEURISTICS line: route-start timeout must cover one validation screenshot,
  but not justify salvaging an over-gate branch.

## 2026-06-21 Pinnacle Existing-Preview Guard Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- Speed runner attempts abandoned/restarted stale route-gated branches and
  created fresh run `20260621_035756_092`.
- Durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/019_after_interrupted_speed_035756.png`
  showed the Pinnacle island map at visible timer `0:00:37`.
- Guarded resume command:
  `python3 game_loop.py lightning_segment --time-limit 2 --route-auto-start --route-routing lightning_war --route-start-mode dialogue-region-repeat-preview-board --strict-route-match`
  stopped safely before Start Mission.
- Segment stop:
  `LIGHTNING_SEGMENT_STOPPED / route_auto_start_not_allowed`; route-start
  result `route_preview_mission_unverified_before_start`; visible preview OCR
  reason `no_known_preview_text_match`.
- The OCR text for that preview block was pause-menu text (`Timeline Playtime`,
  `SAVE and QUIT`, `Easy`, `Base Content`), not mission-preview text.
- Follow-up durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/020_after_segment_resume_035756_route_block.png`
  showed the map still visible at `0:00:38`.

Action taken:

- Tightened `_lightning_visible_ui_has_existing_mission_preview` so only
  concrete `visible_ui == mission_preview_panel` proves an existing preview.
- Added a regression showing pause-menu `classifier_visible_ui` /
  `pause_ocr_override` hints do not schedule preview-only route validation when
  actual evidence is island map.
- Kept stale bridge preview usage as veto-only under concrete preview proof.
- Verified syntax and focused existing-preview/preview-only tests.

Decision:

- Do not click Start Mission from the current map labels or pause-menu OCR.
- The current branch is still under gate at `0:00:38`; run one guarded resume
  after the fix before abandoning it.

Memory compressor:

- Rule to keep: existing-preview validation needs actual mission-preview UI
  proof, not pause-menu classifier metadata.
- Mistake to avoid: OCRing the pause overlay and treating those words as a
  failed mission-preview vocabulary match.
- Faster decision procedure: if `visible_preview_ocr.texts` are pause-menu
  items, fix snapshot/preview authority before spending another route attempt.
- Thing to test next: live guarded segment after the tightened preview guard.
- HEURISTICS line: classifier-only pause hints can block or explain confusion,
  but they must not authorize existing-preview route validation.

## 2026-06-21 Route-Gate Restart And Metadata Patch Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- Fresh durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/021_pre_resume_after_guard_fix.png`
  showed the Pinnacle map at visible timer about `0:00:38`.
- Guarded segment after the false-preview fix operated from the island map and
  stopped at `route_start_subcall_timeout`, proving the pause-menu preview
  false positive was cleared.
- Follow-up proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/022_after_start_panel_guard_timeout.png`
  showed the branch still on the map at about `0:01:11`.
- Runner changes then live-proved safe restart behavior: the old Pinnacle
  branch was abandoned, a fresh R.S.T. run was created, Cataclysm preview text
  was captured around `0:01:17`, and that route gate was abandoned.
- The runner was interrupted while writing manifest metadata; stack evidence
  pointed at `_get_solver_version()` waiting inside a Git subprocess.
- Fresh classify proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/023_after_timeout_restart_interrupt_classify.png`
  showed Detritus island info at visible timer `0:02:24`.
- After patching metadata lookup, a speed run returned quickly but stopped at
  `BLOCKED_UNPAUSED_CLOCK_TICKING / initial_state_not_safe_to_think`.
- Latest durable proof
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/024_after_metadata_patch_speed_blocked_deployment_phase.png`
  showed Detritus Head Office dialogue/deployment at visible timer `0:05:29`.

Action taken:

- Added runner pre-start route-gate handling for
  `route_preview_not_opened_before_start`.
- Allowed restart after `route_start_subcall_timeout` only when timeout
  evidence is preview-only/precombat and the segment never entered combat.
- Replaced `_get_solver_version()` Git subprocess use with direct `.git/HEAD`,
  branch ref, packed-ref, and worktree file reads.
- Added focused tests for Git-hash file reading and no-subprocess solver
  version lookup.
- Verified syntax plus focused Lightning war-tools and runner route-gate tests.

Decision:

- Do not continue the Detritus branch. It is screenshot-proven over `0:03:00`
  before useful first-mission progress.
- Next live action is `lightning_abandon_to_setup` with reason
  `first_mission_segment_over_3m_detritus_0529`, then a fresh speed runner
  after setup proof.

Memory compressor:

- Rule to keep: Git metadata is not part of gameplay and must never block a
  timed live loop.
- Mistake to avoid: trying to salvage deployment/dialogue after screenshot
  proof already exceeds `0:03:00`.
- Faster decision procedure: classify route time leaks as route gate, metadata
  stall, or deployment dialogue; reset immediately once visible proof crosses
  the segment gate.
- Thing to test next: whether `lightning_abandon_to_setup` recovers cleanly
  from Detritus deployment/dialogue and returns to new-game setup.
- HEURISTICS line: over-3:00 first-mission dialogue/deployment means reset, not
  route tuning or combat continuation.

## 2026-06-21 Reset, Tides OCR, And External Prompt Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- Reset attempt from Detritus dialogue first blocked on
  `visible_panel_should_be_cleared_first`; durable proof
  `025_abandon_blocked_detritus_dialogue_1035.png` showed the dead branch at
  `0:10:35`.
- `lightning_ui handle_screen` cleared the Detritus Head Office panel; durable
  proof `026_after_detritus_dialogue_clear_map_1129.png` showed the map at
  `0:11:29`.
- Second reset succeeded: `OK / abandoned_to_new_game_setup`; setup proof saved
  as `027_after_abandon_to_new_game_setup.png`.
- Fresh speed run created Archive run `20260621_045149_516`; durable proof
  `028_speed_archive_route_preview_not_opened_pause_0112.png` showed the pause
  menu at `0h 1m 12s` after route candidate 0 failed to open a preview.
- Offset route probe selected candidate 1 and opened `Mission_Tides`; the
  preview OCR matched Tidal Waves, but speed routing blocked because
  OCR-only starts were previously baseline-only.
- After the Tides OCR patch, a follow-up segment stopped on
  `bridge_snapshot_unavailable`, and the branch was no longer worth salvaging.
- A later speed attempt was interrupted after hanging inside bridge island-map
  pause-peek/screenshot work. Fresh classify proof
  `030_external_privacy_prompt_after_runner_interrupt.png` showed a macOS
  privacy prompt over the pause menu.

Action taken:

- Added `_LIGHTNING_ROUTE_OCR_SPEED_START_MISSIONS = {"Mission_Tides"}`.
- Updated `_lightning_visible_preview_ocr_start_authorized()` so Lightning War
  can start only allowlisted OCR-proven missions, still subject to normal route
  vetoes.
- Added/updated tests proving non-allowlisted OCR-only speed starts remain
  blocked and `Mission_Tides` OCR can start only with matching post-start
  deployment proof.
- Verified syntax and focused tests.
- Stopped live automation on the external macOS prompt.

Decision:

- Do not click the external prompt automatically.
- User must clear the macOS privacy prompt, then the next live command must be
  `lightning_ui classify --include-ocr`.

Memory compressor:

- Rule to keep: `Mission_Tides` visible OCR is a narrow Lightning War start
  authority; other OCR-only speed starts remain blocked unless explicitly
  allowlisted and tested.
- Mistake to avoid: continuing automation when macOS privacy UI is on top of
  the game.
- Faster decision procedure: if a preferred Tides preview is visible and OCR
  proves it, commit through route_start and verify deployment mission id; if an
  external prompt appears, stop immediately.
- Thing to test next: after the prompt is cleared, classify current state and
  decide whether the branch is still under `0:03:00` or must be reset.
- HEURISTICS line: external macOS prompts stop all live Lightning commands until
  the user resolves them.

## 2026-06-21 Privacy Prompt Repeat / OCR Override Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- A single classify/OCR command showed the same macOS private-window prompt
  still covering the pause menu.
- Durable proof saved as
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/031_privacy_prompt_still_visible_resume.png`.
- The classifier result reported `visible_ui: pause_menu`, but OCR text clearly
  contained `"Codex" is requesting to bypass`, `the system private window`,
  `screen and audio`, `Allow`, and `Open System Settings`.
- This is the second consecutive goal turn with the same external prompt
  blocker visible.

Action taken:

- Added OCR-based system prompt promotion:
  `_lightning_attach_visible_ocr()` now applies
  `_lightning_apply_system_prompt_ocr_override()` before pause-menu OCR
  override.
- `_lightning_external_system_prompt_visible()` now also recognizes the
  private-window prompt from attached OCR text.
- Added a regression proving that prompt OCR promotes `pause_menu` to
  `system_privacy_prompt` and does not add `pause_ocr_override`.
- Verified syntax and focused privacy/Tides/route-start tests:
  `28 passed, 461 deselected`.

Decision:

- Do not click the external prompt automatically.
- Do not run route, deployment, combat, or autonomous runner commands while the
  prompt remains visible.
- Next live action after user clears the prompt is a single
  `lightning_ui classify --include-ocr`.

Memory compressor:

- Rule to keep: external prompt OCR beats pause-menu OCR; `ABANDON TIMELINE`
  behind a macOS prompt does not make the game safe to automate.
- Mistake to avoid: treating a screenshot with private-window prompt text as a
  normal pause menu just because the underlying ITB menu is visible.
- Faster decision procedure: if OCR sees `private window` and `screen and
  audio`, stop as `system_privacy_prompt` before any runner or UI click.
- Thing to test next: user clears prompt, then classify current state and timer.
- HEURISTICS line: private-window prompt OCR is sufficient external-prompt
  evidence even when image-only prompt scoring misses.

## 2026-06-21 Blocked Audit: External Privacy Prompt 3/3

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- A fresh single classify/OCR command reported `visible_ui:
  system_privacy_prompt`, `recommended_control: None`, and
  `requires_user_authorization: true`.
- OCR still showed the macOS private-window prompt text, including `bypass`,
  `system private window`, `screen and audio`, `Allow`, and
  `Open System Settings`.
- Durable proof saved as
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/032_privacy_prompt_still_visible_blocked_audit.png`.
- This is the third consecutive goal turn with the same external prompt
  blocker visible.

Action taken:

- Copied the latest classify screenshot into the run notes as proof `032`.
- Updated STATE, STRATEGY, BLOCKERS, EVAL, NEXT, and LOG to record repeat
  count `3/3`.
- Did not click the macOS prompt and did not run route, deployment, combat, or
  autonomous runner commands.

Decision:

- The strict blocked-audit threshold is met. Live Lightning War progress is at
  an impasse until the user resolves the macOS privacy prompt.
- After the prompt is cleared, resume with one fresh
  `python3 game_loop.py lightning_ui classify --include-ocr`.

Memory compressor:

- Rule to keep: repeated external prompt proof at `3/3` means mark the goal
  blocked rather than continuing to poll or clicking external UI.
- Mistake to avoid: spending more live/UI commands while a user-authorization
  prompt is still proven visible.
- Faster decision procedure: if classify returns `system_privacy_prompt` with
  `requires_user_authorization: true`, stop immediately and wait for user
  resolution.
- Thing to test next: once the user clears the prompt, classify current state
  and decide resume versus reset using screenshot/OCR timer only.
- HEURISTICS line: external prompt blockers are solved by user authorization,
  not by automation retries.

## 2026-06-21 Prompt Cleared / Speed Attempts / Route Handoff Bottleneck

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- User cleared the macOS privacy prompt. Fresh classify/OCR proof
  `033_privacy_cleared_pause_menu_timer.png` showed a normal pause menu at
  `0:01:43`.
- Resume segment cleared stale dialogue/preview UI, then stopped on
  `attempt_subcall_timeout`; proof `034_after_segment_timeout_pause_0207.png`.
- Second guarded resume stopped on `first_mission_route_start_pace_gate` at
  `0:02:19`; proof `035_route_start_pace_gate_pause_0219.png`.
- That dead branch was abandoned to setup; proof
  `036_after_route_gate_abandon_to_setup.png`.
- Fresh speed autonomous run attempted three timelines:
  `20260621_100528_857` Archive stopped on
  `route_preview_not_opened_before_start`; `20260621_100814_317` R.S.T.
  vetoed `Mission_Airstrike` then stopped on `route_start_subcall_timeout`;
  `20260621_101117_040` Pinnacle stopped on
  `route_auto_start_not_allowed` /
  `bridge_snapshot_unavailable_visible_island_map`.
- Final safety action was `lightning_ui ensure_pause`; durable proof saved as
  `037_final_speed_attempt_pause_0058.png`.

Action taken:

- Preserved proofs `033` through `037`.
- Allowed the speed runner to reset dead attempts rather than taking manual
  route clicks.
- Stopped after final route-handoff ambiguity and paused the game.
- Updated STATE, STRATEGY, BLOCKERS, EVAL, NEXT, HEURISTICS, and LOG.

Decision:

- Do not continue the current Pinnacle branch into Start Mission. There is no
  verified route identity or safe handoff.
- Next loop should inspect route telemetry/click targeting locally, then reset
  from setup before another speed burst.

Memory compressor:

- Rule to keep: timer headroom does not authorize Start Mission if route
  identity/handoff proof is missing.
- Mistake to avoid: repeatedly spending speed attempts on the same route preview
  click/bridge-snapshot failure without inspecting telemetry.
- Faster decision procedure: after `route_auto_start_not_allowed`, pause,
  preserve proof, inspect recordings, then reset; do not resume blindly.
- Thing to test next: route preview target selection and bridge snapshot
  availability on the first island map, especially Pinnacle/R.S.T. route labels.
- HEURISTICS line: route-handoff ambiguity is a route tooling problem, not a
  combat problem.

## 2026-06-21 Route Handoff Patch

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence reviewed:

- Dalton's route/log review found a route proof handoff bug, not a solver
  problem.
- Archive lost its preview on an unassigned live-preview probe.
- R.S.T. correctly vetoed `Mission_Airstrike`, but the retry after a segment
  wall cap kept only route index and lost click coordinates/preview-closing
  context.
- Pinnacle stopped on a visible map frame that matched first-island/world-map
  context, not a proven mission route map.
- Latest live proof remains
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/037_final_speed_attempt_pause_0058.png`;
  no live command was run after the patch.

Action taken:

- Added full `route_start_pending_context` output from `lightning_segment`.
- Updated `lightning_runner` to carry that context into the next route-start
  retry.
- Added a speed route-start subcall floor so screenshot/OCR validation is not
  starved by the segment wall cap.
- Added first-island/world-map evidence detection when visible island-map UI has
  zero extracted red mission regions.
- Added one retry for first-island clicks that remain on the world map, then a
  block that avoids recording `current_island`.
- Updated STATE, STRATEGY, HEURISTICS, EVAL, BLOCKERS, NEXT, and LOG.

Verification:

- `python3 -m py_compile src/loop/commands.py src/loop/lightning_runner.py game_loop.py`
  passed.
- Focused route-handoff/world-map tests passed: `4 passed`.
- Expanded focused selection passed: `6 passed, 724 deselected`.
- Broader module tests still show unrelated existing failures in OCR candidate
  observations and pace-event failure handling.

Decision:

- The current branch remains evidence only. First live command is still
  `python3 game_loop.py lightning_ui classify --include-ocr`.
- If that classify does not prove a safe mission route identity, abandon/reset
  before the next speed run.

Memory compressor:

- Rule to keep: pending route-start retry needs full context, not just visual
  index.
- Mistake to avoid: recording `current_island` from a four-corp/first-island
  map that has zero visible mission red regions.
- Faster decision procedure: classify once, reset if still ambiguous, then run
  the speed ladder with the patched handoff.
- Thing to test next: whether R.S.T. route retries preserve coordinates and
  whether Pinnacle first-island selection now retries/blocks correctly.
- HEURISTICS line: `island_map_or_unknown` plus zero route regions is
  first-island/world-map evidence, not mission route proof.

## 2026-06-21 Speed Attempt 3 Picker-Wait Patch

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- Ran `python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3`.
- Attempts 1 and 2 reset safely after route identity blocks.
- Attempt 3 selected Pinnacle but stopped as
  `first_island_selection_pending_unverified`.
- Fresh proof: `run_notes/lightning_war_smoke_2026-06-21/screenshots/045_after_speed_attempt3_first_island_pending_pause_0046.png`.
- OCR text on Timeline Playtime was `Oh Om 465`, visible `0h 0m 46s`.

Action taken:

- Added a first-island picker wait before the new-run island coordinate click.
- The wait rejects external prompts, pause overlays, and dark transition frames.
- Added tests for waiting through a dark transition and blocking before island
  click when picker proof never appears.

Verification:

- Focused Lightning start/selection tests: `23 passed, 484 deselected in 16.73s`.
- `python3 -m py_compile src/loop/commands.py game_loop.py src/control/mac_click.py`
  passed.

Decision:

- The paused attempt was first-island ambiguous, so it was abandoned back to
  `new_game_setup`. Reset proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/046_after_attempt3_reset_to_new_game_setup.png`.

Memory compressor:

- Rule to keep: dark setup-transition frames are not first-island picker proof.
- Mistake to avoid: clicking Pinnacle/Archive/R.S.T./Detritus immediately after
  setup Start while the screen is still dark.
- Faster decision procedure: if picker wait times out, block/reset before any
  island coordinate click.
- Thing to test next: route identity extraction for multi-label R.S.T./Pinnacle
  route maps.
- HEURISTICS line: after setup Start, wait for a non-dark picker before the
  first island click.

## 2026-06-21 Speed Run 20260621_130811_734

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- Speed runner reached Archive and captured visible timer `0:00:52`.
- Route map labels were `Restoration Center` and `Forgotten Hills`; the runner
  stopped before Start Mission with
  `multi_region_live_preview_probe_without_route_identity`.
- Restart selected Detritus while requesting R.S.T.; proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/052_route_gate_failed_archive_then_unverified_rst_restart.png`.
- Cleared the Detritus panel and reset to setup; proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/053_after_wrong_detritus_reset_to_setup.png`.

Action taken:

- Added first-island corp-panel OCR fallback and title-first identity matching.
- Removed dialogue-only `R.S.T.` as corp identity authority when the selected
  panel title says Detritus.
- Allowed distinct OCR-labeled multi-region live-preview probes to select one
  visual index while preserving opened-preview validation before Start Mission.
- Kept unlabeled/duplicate multi-region probes blocked.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused pytest selected 11 tests and all passed.

Memory compressor:

- Rule to keep: route labels are probe-selection evidence only, not mission
  identity.
- Mistake to avoid: treating first-island dialogue text as selected corp proof.
- Faster decision procedure: from setup, run one speed burst; if distinct route
  labels appear, let the visual-index probe validate or block.

## 2026-06-21 Click Release And Route Start Safe Probe Patch

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- The old final setup Start click could release over Detritus; proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/054_start_release_detritus_mismatch_guard.png`.
- The wrong Detritus branch was reset safely; proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/055_after_start_release_mismatch_reset_to_setup.png`.
- A fresh speed burst produced route-start timeouts on Archive and R.S.T., then
  stopped on Pinnacle `first_island_selection_pending_unverified`; latest pause
  proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/056_after_click_release_speed_attempts_pause_0055.png`.
- Final live state is verified `new_game_setup`; proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/057_new_game_setup_after_route_start_patch.png`.

Action taken:

- Added click press/release separation for macOS setup-modal Start so the press
  lands on Start and the release lands away from Detritus.
- Changed Lightning War route-start normalization so legacy
  `dialogue-region-repeat-preview-board` requests use visible-text Start
  Mission after safe preview validation, even for unknown-mission safe probes.
- Preserved the preview-only safety gate before any unknown mission commit.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route-start pytest selected 5 tests and all passed.
- Broader route-start pytest selected 9 tests and all passed.

Memory compressor:

- Rule to keep: for Lightning safe auto-start probes, reduce legacy
  dialogue/board proof work before increasing timeout floors.
- Mistake to avoid: treating route-start timeout as only a budget problem when
  the commit path is still using a slower fallback mode.
- Faster decision procedure: from setup, run one speed burst and let the
  visible-text safe probe prove whether the route-start bottleneck is fixed.

## 2026-06-21 Speed Floor Route-Start Patch

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- `recordings/20260621_140134_882` selected Archive, captured visible timer
  `0:01:00`, reached route-ready, then stopped on
  `route_start_subcall_timeout` with a `12.0s` route-start subcall.
- `recordings/20260621_140520_950` selected R.S.T., captured visible timer
  `0:00:47`, reached route-ready, then stopped on
  `route_start_subcall_timeout` with a `12.01s` route-start subcall.
- `recordings/20260621_140835_583` started Pinnacle but blocked on
  `first_island_selection_pending_unverified`.
- Final paused timer proof before reset:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/058_after_140520_speed_pause_0056.png`.
- Final reset proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/059_new_game_setup_after_140520_reset.png`.

Action taken:

- Raised `_LIGHTNING_ROUTE_START_SPEED_MIN_SUBCALL_SECONDS` from `12.0` to
  `30.0` so speed route-start has enough time for one full
  preview/OCR/start-validation cycle.
- Added a regression for a speed segment where route-ready work leaves only
  `12s` under the ordinary wall cap; route-start still receives the full speed
  validation floor.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused timeout pytest selected 3 tests and all passed.
- Broader route-start pytest selected 10 tests and all passed.

Memory compressor:

- Rule to keep: when route-ready repeats under visible timer pace but
  route-start times out at `12s`, raise the route-start validation floor before
  changing route policy.
- Mistake to avoid: letting the speed wall cap masquerade as mission safety
  when the screen timer still has ample first-route headroom.
- Faster decision procedure: from setup, run one speed burst; if route-start
  still times out with the `30s` floor, inspect route-start internals rather
  than adding more generic time.

## 2026-06-21 Mission Force OCR Start Patch

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- `recordings/20260621_141844_457` selected Archive, captured visible timer
  `0:01:01`, reached route-ready, then blocked on
  `route_preview_not_opened_before_start`.
- `recordings/20260621_142331_559` selected R.S.T., captured visible timer
  `0:00:47`, reached route-ready, and OCR-proved `Mission_Force` from
  `defensive shields active`, but blocked because Force was not yet in the
  speed OCR start allowlist.
- The same R.S.T. branch retried and correctly vetoed `Mission_Solar`.
- Final failed-branch timer proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/060_after_142331_speed_pause_0233.png`.
- Final reset proof:
  `run_notes/lightning_war_smoke_2026-06-21/screenshots/061_new_game_setup_after_142331_reset.png`.

Action taken:

- Added `Mission_Force` to `_LIGHTNING_ROUTE_OCR_SPEED_START_MISSIONS`.
- Converted the Force visible-OCR route-start regression from blocking to
  starting only after visible Start Mission and post-start mission-id proof.
- Kept `Mission_Solar` and other speed-vetoed missions blocked.
- Added route-segment test isolation from the live first-route timer gate.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused OCR/veto route-start pytest selected 18 tests and all passed.

Memory compressor:

- Rule to keep: widen OCR start authority only for distinctive, non-vetoed
  previews with live post-start mission proof.
- Mistake to avoid: treating any OCR-recognized preview as start authority;
  `Mission_Solar` remains veto-only.
- Faster decision procedure: from setup, rerun speed. If Force appears again,
  expect the runner to click visible Start Mission and then verify the live
  mission id before deployment/combat.

## 2026-06-21 Force Preview Timeout Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- Patched speed run `20260621_151619_157` selected Archive and reached
  route-ready, then stopped on route-start timeout around visible timer
  `0:00:57`.
- Rehomed run `20260621_152033_644` selected R.S.T. The first preview OCR
  identified `Mission_Bomb`, correctly vetoed it, and preserved pending retry
  context.
- The retry reached a Force preview. Telemetry OCR saw `Turbine Cluster`,
  `Defensive Shields Activel`, `Take less than 3 Grid Damage`, and timer text
  `1 0:01:38`.
- Route-start then timed out before visible Start Mission or deployment proof.
- Final cleanup branch blocked on Pinnacle
  `first_island_selection_pending_unverified`; durable failed-branch proof is
  screenshot `067` with OCR `Oh Om 555` (`0:00:55`), and final setup proof is
  screenshot `068`.

Action taken:

- Reset the final dead branch to verified setup.
- Recorded that OCR-label clicking is live-proven for preview opening.
- Promoted the next bottleneck to route-start commit/handoff after allowlisted
  Force OCR.

Memory compressor:

- Rule to keep: Force OCR must lead to visible Start Mission and post-start
  proof quickly, or produce an exact pending safe-preview handoff.
- Mistake to avoid: rerunning speed immediately from setup and spending another
  attempt on the same route-start timeout.
- Faster decision procedure: patch the Force-preview commit path, add focused
  tests, then rerun speed from setup proof `068`.

## 2026-06-21 Volatile Fast-Veto And Tides Overrun Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- Failed Archive branch `20260621_172222_055` was paused and preserved at
  screenshot `076`, OCR `Oh 2m 225` -> `0:02:22`.
- Code patch made opened-preview OCR run before slow post-preview route
  recommendation refresh, added `Protect the Power Generator` as Volatile OCR
  vocabulary, and retry-suppressed `Mission_Volatile`.
- Fresh speed branch `20260621_174517_429` verified Easy/Base Content OFF,
  selected Archive, and captured first-island timer proof `0:01:06`.
- Candidate 0 failed `route_preview_not_opened_before_start`; retry started
  OCR-authorized `Mission_Tides`.
- Runner stopped on `deployment_visible_ui_not_deployment`: visible UI was a
  deployment screen while bridge phase reported `combat_enemy`.
- Manual recovery used `deploy_recommended`: Electric F5, Wall/Hook E6,
  Rock/Boulder C6; all verified, then deployment Confirm clicked.
- `lightning_loop --time-limit 2 --speed-loss-policy` completed Tides combat
  safely, but visible pause-menu timer proofs reached `0:04:06`, `0:04:40`,
  and `0:05:11`. Screenshot `077` preserves the failed segment proof.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route/OCR pytest selected 9 tests and all passed.
- Focused route-probe regression pytest selected 6 tests and all passed.
- Focused runner island-cycle pytest selected 1 test and passed.
- `git diff --check -- src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.

Memory compressor:

- Rule to keep: visible OCR veto evidence may block quickly before slow refresh,
  but it is not Start Mission authority.
- Mistake to avoid: after screenshot/OCR proves a first mission segment over
  `0:03:00`, do not spend more live proof clicks on that branch.
- Faster decision procedure: reset dead branch to setup, then patch the
  deployment handoff so visible deployment screens can deploy/confirm inside
  the runner even when bridge phase still says `combat_enemy`.

## 2026-06-21 Airstrike OCR Narrowing And Prompt Stop Loop

Goal restated: earn Lightning War with Blitzkrieg by completing the first two
Corporate Islands under `0:30:00`, with each mission segment under `0:03:00`
by screenshot/OCR timer proof only.

Evidence:

- Reset the older `0:02:08` branch to setup, then ran the speed ladder:
  `python3 game_loop.py lightning_autonomous --mode speed --target-islands 2 --max-attempts 3`.
- Attempt `20260621_224439_478` selected Archive candidate 0 and safely vetoed
  `Mission_Airstrike` before Start. Screenshot `107` preserves stronger
  terminal pause timer proof `0:01:39`; screenshot `104` is an auxiliary
  later/rehome frame at `0:01:14`.
- Attempt `20260621_224949_737` selected R.S.T. candidate 1 and blocked before
  Start on `conflicting_known_preview_text_matches`. Screenshot `108`
  preserves stronger terminal pause timer proof `0:01:49`; telemetry logged
  `0:01:14`, and screenshot `105` is an auxiliary later/rehome frame at
  `0:01:00`.
- Attempt `20260621_225418_964` applied the Archive route-probe cache, pruned
  candidate 0, tried candidate 1, hit the same OCR conflict, then stopped on a
  real macOS private-window/screen-audio prompt. Screenshot `106` preserves the
  prompt and visible timer `0:01:35`.

Action taken:

- Diagnosed the conflict as Tides preview text plus `Protect the Emergency
  Batteries`; emergency batteries are not unique Airstrike mission identity.
- Removed `protect the emergency batteries` and `emergency batteries` from
  Airstrike visible-preview OCR patterns.
- Added a regression proving Tides plus emergency-battery text resolves to
  `Mission_Tides`, not Airstrike.
- Added a direct regression proving emergency-battery objective text alone
  remains `UNKNOWN`.
- Preserved proof screenshots `104`, `105`, `106`, `107`, and `108`; prefer
  `107`, `108`, and `106` for the terminal timer trail.
- Ignored stale `conflicting_known_preview_text_matches` hard-prune cache
  entries from the pre-fix matcher, so a now-clean Tides preview is not skipped.
- Wired standalone `cmd_lightning_segment(route_auto_start=True)` to consume
  and save `RunSession.lightning_route_probe_cache`.
- Tightened cache recording so successful route starts do not add skipped
  records and dry-runs do not mutate route-probe cache.
- Added a guard proving explicit `route_probe_cache` arguments bypass session
  cache loading/merging.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route/OCR/cache pytest passed with `14 passed, 535 deselected`.

Memory compressor:

- Rule to keep: `Protect the Emergency Batteries` is bonus/objective text, not
  Airstrike identity. Airstrike OCR identity should rely on `air support`.
- Guardrail to keep: emergency-battery text by itself must remain `UNKNOWN`,
  causing a safe block instead of a false veto/start identity.
- Rule to keep: route-probe cache helps choose which preview to inspect next;
  it never authorizes Start Mission.
- Guardrail to keep: only real failed route-start probes should write route
  cache; dry-run and successful route-start paths should leave it alone.
- Guardrail to keep: explicit route-probe cache arguments are authoritative and
  should not be merged with active session cache by surprise.
- Mistake to avoid: do not run another live command while the macOS prompt is
  visible.
- Faster decision procedure: after user resolves the prompt, capture fresh
  proof, reset/recover to verified setup, and rerun speed with the narrowed OCR
  matcher.

## 2026-06-21 Route-Probe Cache Scope Guard

Goal restated: keep compounding the Lightning War runner while live automation
is stopped on the macOS prompt.

Action taken:

- Tightened route-probe cache hard-prune matching so entries require exact
  first-island, routing-mode, and mission-index scope.
- Added a regression proving the same cached failed label prunes inside the
  same route scope but does not prune when scope is missing or the mission
  index changes.
- Extended coverage for mismatched first island, mismatched route routing,
  unscoped cache-entry signatures, and blank session island scope.

Verification:

- `python3 -m py_compile src/loop/commands.py tests/test_lightning_war_tools.py`
  passed.
- Focused route/OCR/cache pytest passed with `16 passed, 535 deselected`.

Memory compressor:

- Guardrail to keep: route-probe cache is selection evidence inside one exact
  route scope. Missing or mismatched first-island/routing/mission-index scope
  must fall back to probing.
- Guardrail to keep: blank session island scope must not apply hard-prune
  cache; probing again is safer than cross-context pruning.
