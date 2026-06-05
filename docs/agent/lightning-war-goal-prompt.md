# Lightning War Goal Prompt

Paste this into `/goal` mode for the autonomous Blitzkrieg Lightning War
speedrun. Keep the pasted prompt under 4000 characters.

```markdown
Goal: Earn Lightning War in Into the Breach with no human help: Blitzkrieg,
Easy, Advanced Edition OFF, first 2 Corporate Islands complete before the
30:00 in-game achievement timer.

Use the "Hybrid Theory" mode from
`docs/agent/lightning-war-autonomous-speedrun.md`: run repeated autonomous
attempts until unlock. Retry normal failures. If telemetry shows a repeated
bottleneck, park in a verified safe state, patch/test the narrow fix, record
the new code version, then continue attempts.

Hard invariant: Python owns every live-clock state. Codex may think, inspect
files, patch code, or use agents only after the bot proves the game is paused
or otherwise non-live. If safe thinking cannot be proven, keep acting
deterministically, pause as soon as possible, or stop with
`BLOCKED_UNPAUSED_CLOCK_TICKING`.

Read/load as needed:
- `AGENTS.md`
- `docs/agent/lightning-war-autonomous-speedrun.md`
- `docs/agent/live-runbook.md`
- `docs/agent/achievement-playbook.md`
- `docs/agent/safety-gates.md`

Build/use the local speedrun stack. Prefer an in-process
`lightning_autonomous` conductor over a Codex/tool loop. Reuse existing
Lightning helpers: `lightning_preflight`, `lightning_segment`,
`lightning_attempt`, `lightning_loop`, `auto_turn`, route validation, pause
guards, panel clearing, bridge combat execution, and calibrated UI controls.
Do not invent a parallel combat executor.

Telemetry is mandatory. For each serious attempt, record JSONL events,
2-second screenshots, contact sheets, interesting-frame deltas, and
`summary.md` under `recordings/<run_id>/telemetry/`. Keep all successful raw
screenshots, drop only under capture backpressure, and do not record video.

Timer policy: use save/profile `current.time` or visible pause-menu Timeline
Playtime; ignore profile `timer`. Measure mission pace start-to-start,
including preview/dialogue, deployment, combat, enemy waits, panels, map
return, shop/leave, and next Start click.

Pace gates: first island must complete before 15:00, no grace. Add/tune a
second-island start gate around 16:30-17:00. Restart full run on wrong setup,
AE mismatch, timer >= 30:00, grid collapse risk, unrecoverable stale
game/bridge state, unresolved research/desync/post-enemy/threat-audit block,
or any state requiring live-clock Codex thinking.

Speed policy: optional objectives, Perfect Island, reputation, stars, pods,
protected-unit losses, mech HP loss, mech death, and KIA are acceptable if the
timeline survives and continuing is faster. Grid/building damage is acceptable
within reason when grid remains above 0 and it does not create compounding
risk. No save rollback; use normal abandon/restart/new-run only.

Routing policy: route for speed, not reputation. Prefer empirically fast
islands/missions once telemetry proves them. If a different mission loads after
a click, play it unless pace/grid gates say the run is already dead. Log the
mismatch so future route code can improve.

Shop/island tail: if grid is below max, buy Grid Power first. If grid is full,
leave immediately. Do not chase optional pilots, weapons, cores, pods, or
speculative installs during the timed route.

Combat policy: solve with normal/long budget only from verified pause. During
live play, execute known-fast deterministic actions, bridge-verified combat,
End Turn clicks, enemy waits, and immediate pause attempts. Do not let Codex
ponder while the clock ticks.

Success proof: visible Lightning War popup or `achievements --sync`; if popup
appears, sync afterward to confirm. Stop only when unlocked, or when parked in
a verified safe state with telemetry, blocker, and exact next action.
```
