# Lightning War Goal Prompt

Paste this into `/goal` mode when preparing a Blitzkrieg Lightning War attempt.

```markdown
Goal: Earn **Lightning War** in Into the Breach: Blitzkrieg squad, Easy difficulty, first 2 Corporate Islands completed under the achievement's 30:00 in-game timer.

This is a speed/routing achievement, not a perfect-island, pod, reputation, or full-run victory goal. Prefer Archive and R.S.T. Do not route to the Volcanic Hive.

Use agents liberally for independent review: Lightning command architecture, Windows Computer Use calibration, safety overrides, routing strategy, and prompt/edge-case critique.

Read first:
- `AGENTS.md`
- `docs/agent/live-runbook.md`
- `docs/agent/safety-gates.md`
- `docs/agent/achievement-playbook.md`
- Lightning War rules around `lightning_preflight`, `lightning_attempt`, `lightning_loop`, `lightning_segment`, `lightning_ui`, `lightning_peek`, and `recommend_mission --routing lightning_war`.

Operate in two modes only:
1. verified paused planning
2. short live execution bursts

Do not begin or resume live play until the next live command is explicit. Do not click Start Mission, End Turn, route regions, panels, or `lightning_segment` live "just to see" before preflight and calibration are clean.

Primary implementation direction:
- Harden and use the existing Lightning War stack.
- Treat `lightning_segment` as the primary runner.
- Treat `lightning_loop` as combat-only.
- Treat `auto_turn` as the sole combat executor/simulator bridge.
- Do not build a parallel screenshot bot or duplicate route scoring, UI classification, deployment, End Turn clicking, dirty gates, safety gates, panel clearing, or bridge combat execution.
- If adding automation, wire it as a normal CLI/helper around existing functions. If calling functions directly, mirror CLI defaults explicitly: `pause_on_stop`, `resume_if_paused`, `auto_clear_panels`, `quiet`, `pause_before_solve`, `pause_between_actions`, and Lightning speed-loss policy.

Windows control rules:
- This run is Windows-based. Do not trust macOS Quartz, `osascript`, Retina, or legacy global coordinates.
- Use Windows Computer Use only for screenshots and calibrated noncombat UI controls.
- Before every UI click, verify the focused/window screenshot is Into the Breach.
- Prefer window-local calibrated controls. Never use blind global guesses.
- UI clicks are for pause/continue, mission/island navigation, deploy confirm, End Turn, rewards, shops, and panels. Combat actions stay bridge-executed.

Pause-first investigation gate:
- Before any research, desync diagnosis, threat-audit review, dirty-plan review, uncertain-board analysis, route thinking, long file/code inspection, or large output, first ensure the visible Into the Breach pause menu is open.
- Verified pause means visible pause-menu evidence on the actual game window, not stale classifier output or quiet terminal output.
- If pause cannot be verified, do not investigate while the timer is running. Perform only the smallest calibrated transition needed to reach a pauseable state, then pause.
- If pause still cannot be verified, stop with `BLOCKED_UNPAUSED_CLOCK_TICKING`.
- Do not run `auto_turn`, wait-heavy bridge commands, or combat commands while sitting in the pause menu. If fresh evidence is essential, pre-plan a bounded micro-live probe: unpause, capture/read once, immediately re-pause, verify pause, then analyze.

Non-pauseable edge cases:
- Deployment may not expose pause. If deployment zones are visible and fewer than 3 mechs are placed, let the Lightning/deploy conductor finish deployment and click calibrated CONFIRM, then wait for `combat_player` with active mechs and pause before planning.
- After End Turn or enemy animations, `combat_player` with `active_mechs == 0` is a transition gap, not a board to solve or diagnose. Wait/retry briefly to active player turn or terminal panel, then pause.
- Reward, promotion, pod, Perfect Island, CEO/dialogue, mission-preview, leave-island, and post-reward map panels can mask stale bridge state. Trust visible panels, clear only known safe panels, then re-pause before routing.

Lightning War override policy:
Relax normal AGENTS stop behavior only for losses that are irrelevant to Lightning War and are modeled by the existing Lightning speed-loss policy:
- failed bonus objectives
- failed Perfect Island conditions
- lost/unrecovered Time Pods
- reputation/star loss
- optional objective failure
- protected-unit loss that does not prevent Region Secured
- ordinary building/grid damage if predicted grid remains above 0

Do not relax:
- timeline collapse or predicted grid <= 0
- KIA, pilot death, mech death, mech HP loss, or mech status loss
- unresolved current research or unknown mechanics
- live desync or post-action verify mismatch
- stale or uncertain board
- bridge/screen contradiction
- `INVESTIGATE`, `INVESTIGATE_POST_ENEMY`, persistent `post_enemy_block`, or uncovered `THREAT_AUDIT_BLOCKED`
- unknown loss kinds
- failed primary objective, Timeline Lost, or Region Secured mismatch

If a gate is only optional-objective/pod/perfect/reputation loss and Lightning speed policy proves the timeline remains alive, classify it as `LIGHTNING_ACCEPTABLE_SPEED_LOSS`, log it, and continue.

Preflight:
- Blitzkrieg squad
- Easy / difficulty `0`
- Advanced Edition ON
- Lightning War target active
- max game speed / timer UI ready
- reliable game timer under 30:00
- no pending research, diagnosis, or post-enemy block
- Windows control calibration verified

Timer:
- Use save/profile `current.time` or visible pause-menu Timeline Playtime.
- Ignore profile `timer`.
- If timer appears to roll backward, use the highest reliable observed timer unless this is clearly a fresh timeline with stale undo data.
- Measure mission pace start-to-start: Start Mission click to next Start Mission click, including deployment, combat, enemy animations, panels, map return, and next preview. Target under 3:00 per mission.

Routing:
- Prefer fast, low-friction missions over reputation.
- Prefer short-turn/plain/train/tidal-style missions when scorer agrees.
- Avoid Satellite, Dam, Bad Repairs/repair platforms, Detritus vats/barrels/disposal/acid tank, Mines/pods, fragile allies, volatile/no-kill, kill-count/kill-limit, spawn-block, Mite, thaw/fire/terraform counters, and slow animation maps unless no fast alternative exists.
- Corporate HQ can appear before active. If preview says `No Vek Detected`, pick the fastest remaining side mission.
- Count an island only after HQ fight plus reward/shop/leave flow are resolved.

Shop / island tail:
- Do not chase Perfect Island. If Perfect Island happens, take the fastest useful reward, usually Grid.
- In shop, buy Grid Power to full first if below max.
- If grid is full, leave quickly unless a trivial core/purchase clearly saves more time than it costs.
- Do not install speculative cores, swap pilots, chase pods, or introduce unknown weapons during the timed route.

Abort/reset:
- Hard reset on wrong setup, preflight FAIL, timer at/over 30:00, grid collapse risk, unresolved research/desync/post-enemy block, or bad slate with no fast route.
- Strongly consider reset if island 1 is not complete by about 16-18 minutes.
- No island complete after 20 minutes is restart territory.

After each burst, report:
- timer
- phase/screen
- pause status / pause guard
- missions and islands complete
- last command
- accepted speed losses
- blocker if any
- exact next recommended command

Definition of done:
- Best case: Lightning War visibly unlocks or `achievements --sync` confirms it.
- Otherwise stop safely paused with a clear blocker, evidence, logs, and exact next action.
```
