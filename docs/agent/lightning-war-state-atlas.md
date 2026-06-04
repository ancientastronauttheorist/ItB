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

`forced_bridge_preview_ambiguous`
- Proof: route recommendation source is `bridge_preview`, there is exactly one
  ranked mission, but the visible red-region detector reports more than one
  candidate blob and no save-backed visual assignment.
- Codex/user work: not allowed while live.
- Action: do not auto-start. Stop at the route decision, collect save-backed
  assignment or a verified single-region preview, then start with an exact
  expected mission id.

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
discovered after Start loads deployment, local automation must recover without
asking Codex: deploy the three mechs, click CONFIRM, verify pause from the first
player turn, abandon the timeline, confirm, select the carry-forward pilot, and
verify `new_game_setup` or another safe state. Do not continue the mismatched
mission for Lightning War.

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
