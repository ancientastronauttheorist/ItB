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

## Must Act Now States

`island_map`, `mission_preview`, `deployment`, `combat_player`,
`enemy_animation`, `reward_tail`, `shop`, `dialogue`, `transition`,
`ambiguous_ui`, `stale_bridge`, and `safety_dirty_block`
- Proof: screen classifier, bridge phase, stale/unknown bridge state, or any
  advancing `current.time`.
- Codex/user work: not allowed while live.
- Action: deterministic conductor path, route-start helper, panel-clear helper,
  deployment/combat loop, or pause guard if the screen is pauseable.

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

When `lightning_pause_guard` returns a top-level result with `last_poll`, the
nested `last_poll` is the evidence-bearing payload. The pre-click panel can be
`reward_panel` while the post-click `pause_verify` is `pause_menu`; the conductor
must treat the latter as the resting state and still retain both screenshots in
the journal.
