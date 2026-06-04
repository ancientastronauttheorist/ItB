# Lightning War Experiments

This log tracks Blitzkrieg Lightning War practice work. Use the pattern:
hypothesis -> segment -> evidence -> result -> derived rule -> code/docs update.

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
