# Lightning War Goal Prompt

Paste this into `/goal` mode for the autonomous Blitzkrieg Lightning War
speedrun. Keep the pasted prompt under 4000 characters.

```markdown
Goal: Earn Lightning War in Into the Breach with no human help: Blitzkrieg,
Easy, Advanced Edition OFF, first 2 Corporate Islands complete before the
30:00 in-game achievement timer.

Primary runner:
`python3 game_loop.py lightning_autonomous --max-attempts 999 --route-auto-start --advanced-content off --difficulty 0`

Use lower-level live commands only to debug the conductor from verified
pause/non-live. Reuse Lightning helpers; do not invent a parallel combat
executor.

Use "Hybrid Theory" mode from
`docs/agent/lightning-war-autonomous-speedrun.md`: repeat attempts until
unlock. Retry normal failures. If telemetry shows a repeated bottleneck, park
safe, patch/test the narrow fix, record code version, then continue.

Hard invariant: Python owns every live-clock state. Codex may think, inspect,
patch, or use agents only after verified pause/non-live. Otherwise Python must
act, pause, restart, or emit a local no-thinking signal.

`BLOCKED_UNPAUSED_CLOCK_TICKING` is not a global `/goal` failure. Dead
attempts, failed pause proof, post-enemy blocks, pace failure, route RNG, stale
bridge/game, and unpausable live states are attempt outcomes. Restart/retry.
Mark `/goal` BLOCKED only if the game cannot launch/control/reach setup, or
after 5 consecutive identical infrastructure recovery failures with telemetry.

Read/load as needed: `AGENTS.md`,
`docs/agent/lightning-war-autonomous-speedrun.md`,
`docs/agent/live-runbook.md`, `docs/agent/achievement-playbook.md`,
`docs/agent/safety-gates.md`.

Telemetry is mandatory: JSONL events, 2-second screenshots, contact sheets,
interesting-frame deltas, and `summary.md` under
`recordings/<run_id>/telemetry/`. Keep all successful screenshots; drop only
under capture backpressure; no video.

Recovery ladder:
1. If a clearable panel is visible, run `lightning_ui handle_screen`.
2. Try `lightning_ui ensure_pause` once.
3. If pause guard says `live_combat_phase` and bridge says
   `phase=combat_player` with `active_mechs > 0`, do not think. Run one burst:
   `python3 game_loop.py lightning_segment --time-limit 2 --max-steps 1 --max-turns 1 --no-pause-before-solve`
4. If the attempt is dead/contaminated by pace, timer, grid collapse, stale
   game/bridge, `POST_ENEMY_AUDIT_MISSED_WINDOW`, or persistent
   `post_enemy_block`, emit best-effort `attempt_dead_unpausable` telemetry
   with latest timer/phase/UI/blocker, then abandon/restart/fresh setup.
   If telemetry write fails, restart anyway.
5. Diagnose/patch only from verified pause/non-live, especially after repeats.

Timer: use save/profile `current.time` or visible pause Timeline Playtime;
ignore profile `timer`. Measure mission pace start-to-start, including
preview/dialogue, deployment, combat, enemy waits, panels, map return, shop,
leave, and next Start click.

Pace gates: island 1 complete before 15:00, no grace. Tune island-2 start gate
around 16:30-17:00. Restart current attempt on wrong setup, AE mismatch, timer
>= 30:00, grid collapse risk, unrecoverable stale state, or live-clock Codex
thinking requirement.

Speed policy: optional objectives, Perfect Island, reputation, stars, pods,
protected-unit losses, and nonlethal mech HP loss are acceptable if timeline
survives and continuing is faster. Mech death/KIA are speed losses only when
current code can safely continue; otherwise restart/patch from safe state.
Grid/building damage is ok when grid stays above 0. No save rollback.

Routing/shop: route for speed, not reputation. Prefer empirically fast
islands/missions. If a different mission loads, play it unless pace/grid gates
say dead. If grid is below max, buy Grid Power first; if full, leave
immediately. Do not chase optional purchases.

Success proof: visible Lightning War popup or `achievements --sync`; if popup
appears, sync afterward. Stop only when unlocked, or when true infrastructure
blocking criteria above are met with telemetry and exact next action.
```
