# Lightning War State Atlas

Authoritative timer: save/profile `current.time` milliseconds. Visible
pause-menu Timeline Playtime may corroborate when the pause menu is visible and
the screenshot is clearly Into the Breach.

## Safe To Think States

`verified_pause`
- Proof: pause-menu classifier, guard JSON, bridge pause signal, or stable
  `current.time`.
- Codex/user work: allowed.
- Examples: planning, tests, docs, diagnosis, commit, push, route review.

`proven_non_live`
- Proof: title/setup/main-menu/post-achievement screen where the Lightning War
  clock has not started or no longer matters.
- Codex/user work: allowed after confirming the screen.

`new_game_setup`
- Proof: visible setup layout with top Back and Start buttons, squad card, and
  setup controls. Classifier should use this explicit layout before considering
  pause-menu crops.
- Codex/user work: allowed. Required actions before Start are achievement sync,
  Blitzkrieg/Easy/AE verification, and focused setup fixes.

`verified_difficulty_setup`
- Proof: `verify_setup --difficulty 0` returns PASS for Easy and all Advanced
  Content rows ON.
- Codex/user work: allowed until the final Start button is clicked.
- Action: use the Python conductor's `--start-from-verified-setup` path so the
  Start click and first live segment happen in one local process. When choosing
  a known first corporation immediately, prefer `--start-island rst` or
  `--start-island archive` so the conductor selects the island, clears the intro,
  clicks Pause, and verifies the pause guard before returning.

## Must Act Now States

`island_map`, `mission_preview`, `deployment`, `combat_player`,
`enemy_animation`, `reward_tail`, `shop`, `dialogue`, `transition`,
`ambiguous_ui`, `stale_bridge`, and `safety_dirty_block`
- Proof: screen classifier, bridge phase, stale/unknown bridge state, or any
  advancing `current.time`.
- Codex/user work: not allowed while live.
- Action: deterministic conductor path, route-start helper, panel-clear helper,
  deployment/combat loop, or pause guard if the screen is pauseable.

`hq_warning_island_map`
- Proof: island map with substantial red territory plus the Hive Leader /
  Corporate HQ warning tooltip. Tooltip crops can resemble perfect-reward
  cards, but the red/green map is authoritative.
- Codex/user work: not allowed while live.
- Action: classify as `island_map` and route/start the HQ mission with the route
  helper or a verified boss-region click.

`island_complete_leave`
- Proof: completed Corporate Island map behind a dark overlay with visible
  `SPEND REPUTATION` and `LEAVE ISLAND` controls. Broad reward or KIA crops may
  score high on this screen, but the leave button plus colored map is
  authoritative.
- Codex/user work: not allowed while live.
- Action: click `leave_island`, then immediately click `leave_confirm_yes` if
  the first click succeeds. Do not clear this screen through generic reward or
  KIA handling.

`mission_preview_dialogue`
- Proof: an open mission preview card is visible, but an advisor textbox hides
  the usual yellow Start Mission text. The R.S.T. Train preview can present this
  way after selecting `Test Site Echo`.
- Codex/user work: not allowed while live.
- Action: classify as `mission_preview_panel` with `dialogue_textbox` as the
  first control. The segment loop should dismiss the textbox, re-read the
  preview, then click Start Mission without returning to Codex.

`forced_bridge_preview_ambiguous`
- Proof: route recommendation source is `bridge_preview`, there is exactly one
  ranked mission, but the visible red-region detector reports more than one
  candidate blob and no save-backed visual assignment.
- Codex/user work: not allowed while live.
- Action: do not auto-start. Stop at the route decision, collect save-backed
  assignment or a verified single-region preview, then start with an exact
  expected mission id.

`explicit_route_start_without_target`
- Proof: an explicit `lightning_segment --route-visual-region-index N` was run
  from verified pause without `--route-target-mission-id`; the intended save
  target was `Mission_Armored_Train`, but the clicked region loaded
  `Mission_ForestFire`.
- Codex/user work: not allowed while live.
- Action: infer the save-ranked target from the route recommendation and
  validate the mission preview before clicking Start Mission. If the preview id
  mismatches or is unavailable, block before deployment instead of continuing
  the wrong mission.

`hard_veto_route_preview`
- Proof: after a manual visual route preview, bridge-preview reports one of
  `Mission_Artillery`, `Mission_Dam`, `Mission_ForestFire`, or
  `Mission_Volatile` while no exact expected mission id was supplied.
- Codex/user work: not allowed while live.
- Action: do not click Start Mission. The route-start helper must block before
  Start, verify pause, and choose another visible region or restart the
  timeline.

`live_combat_phase_pause_fallback`
- Proof: `lightning_pause_guard` can return `live_combat_phase` while the
  bridge reports `phase=combat_player`, `active_mechs > 0`, and the screen is
  live combat.
- Codex/user work: not allowed.
- Action: do not stop to think. Treat the bridge state as actionable, skip
  pause-only solving for that turn, and run the local solve/execute loop
  immediately with `wait_for_turn=false`.

`forest_fire_post_enemy_miss`
- Proof: Archive `Mission_ForestFire`, mission index 6, turn 2, record
  `recordings/lw/m06_turn_02_post_enemy.json`; predicted enemy phase killed all
  enemies and left no mech Fire, but bridge outcome had one enemy alive and
  WallMech on Fire.
- Codex/user work: allowed only from verified pause or after abandoning the
  attempt.
- Action: do not advance that board until the post-enemy block is investigated
  or the attempt is abandoned. Route picker should strongly avoid Forest Fire
  for Lightning War because this mismatch creates expensive diagnosis friction.

## Watchdog Evidence Fields

The outer conductor journal should preserve:
- `safe_to_think`, `must_act_now`, and `clock_state`.
- Current/effective timer and any timer-probe deltas.
- `pause_verified`, `timer_stop_verified`, and `timer_running`.
- Visible UI name, screenshot path, classifier crop scores, and guard JSON path.
- Compact bridge state: status, phase, turn, active mechs, deployment-zone
  count, island-map count, and active-mission flag.
- Pause-guard decision: status, reason, and whether pause was allowed.

## Important Distinctions

`pause_clicked` is an action label, not proof. It becomes safe only when paired
with `pause_verified=true`, `timer_stop_verified=true`, a verified pause-menu
classifier result, a bridge pause signal, or stable `current.time`.

`new_game_setup` is safe but is not a pause menu. Do not click `menu_continue`
or run a live segment from setup just because a dark screenshot has a
pause-like crop. Verify setup, then Start intentionally.

The final Difficulty Setup Start click begins the achievement clock. After that
click, the conductor must own routing/island/deployment/combat immediately; do
not return control to Codex between Start and the first deterministic segment.
For a fresh R.S.T. or Archive attempt, this includes the corporation click and
bottom-right intro Continue; a clicked Pause is still not proof until the guard
classifies a safe resting state.

Turn-0 deployment is normally not pauseable. If a route-start mismatch is only
discovered after Start loads deployment, local automation must first classify
the actual mission. If the post-start bridge snapshot is an active mission, the
grid is above zero, and the actual mission is not a Lightning War hard veto,
continue with the actual loaded mission and update the route guard to that
mission. If the actual mission is a hard veto or the state is not playable,
recover without asking Codex: deploy the three mechs, click CONFIRM, verify
pause from the first player turn, abandon the timeline, confirm, select the
carry-forward pilot, and verify `new_game_setup` or another safe state.

For Windows Timeline Lost recovery, the first carry-forward pilot portrait is
calibrated near window `(500,329)`. The older `(490,329)` point can land between
portraits and leave the panel open.

If the post-start mismatch recovery deploys and clicks CONFIRM but pause
verification still sees `deployment_screen` with
`recommended_control=deploy_confirm`, this is a sticky CONFIRM state. It is
still `must_act_now`: click CONFIRM once more, wait briefly, and retry verified
pause before abandoning.

When `lightning_pause_guard` returns a top-level result with `last_poll`, the
nested `last_poll` is the evidence-bearing payload. The pre-click panel can be
`reward_panel` while the post-click `pause_verify` is `pause_menu`; the conductor
must treat the latter as the resting state and still retain both screenshots in
the journal.

An explicit visual route click is not enough route proof. The segment should
carry either the user-supplied `--route-target-mission-id` or the inferred
save-ranked target into preview validation and into the immediate
deployment/combat attempt.

`ambiguous_bridge_preview_route`
- Proof: Archive start with two visible red regions at `current.time=0:01:26`.
  The bridge-preview candidate reported `Mission_Volatile`, but visual region
  0 loaded `Mission_Artillery`; see
  `recordings/20260604_060138_355/lightning_route_mismatch.json`.
- Codex/user work: allowed only after recovery parks at verified setup/pause.
- Action: if multiple red regions are visible and the only mission id comes
  from `source=bridge_preview`, do not copy that id into every visual-region
  command as an exact target. Use a save-backed region assignment, a
  single-region forced preview, or a no-target visual start that accepts the
  actual mission.

`route_preview_hard_veto_before_start` is a safe stop only after the helper has
verified pause. It means the selected region's hidden mission is known to be too
slow or fragile for Lightning War's route budget; resume by selecting a
different red region through the route helper, not by manually clicking Start.

During combat, `live_combat_phase` is a must-act-now signal, not a safe stop.
If the bridge says a player turn is ready and the guard refuses to pause because
combat is live, the conductor must solve from that fresh bridge state instead
of returning to Codex.

`wind_covered_threat_audit`
- Proof: Blitzkrieg Lightning War attempt `20260604_102343_862`,
  R.S.T. `Mission_Wind` turn 2. Scorpion1 at G6 targeted G5 while G6 was in the
  wind row and the bridge exported `environment_wind_dir=0`; Rust predicted the
  pre-attack gust moved the Scorpion to F6, leaving grid/buildings unchanged.
- Codex/user work: allowed only after verified pause. Do not manually click a
  held End Turn unless the bridge has a current wind direction and the
  projected attack no longer hits a live building.
- Action: threat audit projects `Mission_Wind` gusts before attacks. If the
  moved attack is clear, classify `attacker_will_be_moved_by_wind`; if it still
  hits a building, keep blocking as `still_threatened_after_wind`.

`live_boss_preview_overrides_stale_route_target`
- Proof: same attempt after `Mission_Bomb`. Save-backed map assignment labelled
  visual region 2 as `Mission_Wind`, but the live bridge preview exposed
  `Mission_DungBoss` with `forced_boss_route`.
- Codex/user work: do not stop for stale route thinking after a verified boss
  preview; the timer is running or about to run.
- Action: when a bridge-preview top mission is a boss and route status says
  `forced_boss_route`, the route-start helper may override the stale expected
  mission id and click Start Mission. Preserve the override note in logs.

`budget_exceeded`
- Proof: same attempt reached save/profile `current.time=0:30:16`.
- Codex/user work: safe only after verified pause/setup. The attempt is no
  longer viable for Lightning War even if combat can still be won.
- Action: park the game, sync/check achievements if useful, commit verified
  fixes from the safe state, then start a fresh timeline.

`visible_map_overrides_stale_active_mission`
- Proof: Blitzkrieg Lightning War attempt `20260604_163332_450` after R.S.T.
  HQ. The visible screen was an island map / island-selection flow, but bridge
  and session residue still reported an active mission, phase unknown, and
  deployment zones.
- Codex/user work: allowed only after the conductor verifies pause or setup.
  While unpaused on the map, route immediately or pause immediately; do not
  inspect stale bridge state as if combat were still active.
- Action: if the screen classifier reports `island_map` or
  `island_map_or_unknown`, route from visible/save-backed map evidence. Keep
  stale mission/deployment data as a warning field and never deploy from it.

`mission_tanks_post_enemy_leaper_web`
- Proof: same attempt, Archive `Mission_Tanks` turns 1 and 2. Leapers webbed
  RockartMech and WallMech after enemy phase; simulator predicted no web, but
  grid/building/objective and mech HP were unchanged.
- Codex/user work: live combat is not safe to think. Resolve the specific
  post-enemy block only with the fresh bridge state and a reason naming the
  webbed mech and confirming no grid/building/objective delta.
- Action: after resolution, continue from a fresh solve. This is a tactical
  recovery rule, not blanket permission to ignore post-enemy investigations.

`lightning_nonlethal_mech_hp_loss`
- Proof: same attempt, Archive `Mission_Tanks` turn 3. Enemy phase caused
  nonlethal damage to ElectricMech and WallMech while grid/buildings/objective
  remained unchanged.
- Codex/user work: only for Lightning War speed attempts with grid above zero.
  Perfect battle and ordinary achievement runs still block on mech HP loss.
- Action: the speed policy may accept nonlethal mech HP loss as dirty, but must
  keep blocking grid damage, building loss, objective loss, and mech death.
