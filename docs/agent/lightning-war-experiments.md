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
