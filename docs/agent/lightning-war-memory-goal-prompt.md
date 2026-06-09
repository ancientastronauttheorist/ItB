# Lightning War Memory-Aware Goal Prompt

Paste the block below into `/goal`. Prompt length target: under 4000 chars.

```markdown
Goal: unlock "Lightning War". Blitzkrieg. Easy. Finish first 2 Corporate Islands before game timer 30:00. Runner default AE OFF unless user changes and setup verifies. No need full win/perfect/bonuses/pods/rep/clean grid. Need island 2 HQ survived + Steam proof.

Law: AGENTS.md. One session-touching `game_loop.py` command at a time. Fresh bridge/Rust are main truth; stale/desync means stop. Codex slow brain. Codex thinks only after pause/non-live proof. Python owns live clock.

Meta-toggle: pause up = think. pause down = act. Cycle: Codex plans while paused -> Python unpauses and runs exact burst -> Python pauses -> timer stable proof -> Codex may read/analyze. Never blind Esc if already paused; use `ensure_pause`/timer proof. If focus/input bad, Python scancode Esc may pause. If pause proof fails, Python re-pause or stop; Codex no analyze.

Timer proof: user current test says Esc pauses anywhere and stops timer; still prove each time. Findings: pause open froze visible timer; closed advanced it. Probe:
`python scripts/itb_timer_memory_probe.py watch-context --pid <pid> --sample-seconds 5`
`stable` = likely paused, `moving` = live clock. Visible timer strings are best pause proof. Pointer paths/old pause bytes/f32 timer paths are hints only, not durable.

Route: use repo scorer/evidence, not folk wisdom. Prefer Archive/R.S.T. and proven train/plain/low-friction/4-turn missions. Tidal can be fast but risky. Cataclysm/Sandstorm have animation drag. Avoid Satellite, Mines, Bad Repairs, Power Generator, Forest Fire, slow enemies/animations. Target ~3 min start-to-start. Island 1 <15:00. Restart if pace cannot beat 30:00.

Tactics: speed over nice. Ignore optional objectives if slow. Keep grid >0, pilots alive, no mech HP/status/death. Lightning kills clusters. Boulder blocks spawns. Hook/Boulder set whip kills only when obvious. Buy Grid Power first when below max; if safe/full, leave shop fast. Building Chain good. Good pilots: Kazaaakpleth Hook, Camila Lightning, else current best.

Memory: raw strings/GameData can be stale. Rank by freshness/current seed/squad/region. Raw presence not proof. Pilot skills need level gate: skill1 active level>=1, skill2 active level>=2. Skill IDs: 0 HP, 1 Move, 2 Grid DEF, 3 Reactor, 8 Skilled. Grid DEF = base 15 + overflow + active Grid DEF perks.

Run loop: verify Blitzkrieg/Easy/AE/timer/speed. Pick proven route. Validate mission id before Start. Use Lightning runner/`auto_turn` only as resume-aware burst that parks in pause. End Turn only from emitted safe plan. Clear panels/leave shop fast. After island 2 HQ/popup run `python3 game_loop.py achievements --sync`. Goal done only when `unlocked_list` has `Lightning War`; if Steam/offline lag, save evidence, restart/online Steam, re-sync.

Evidence sandwich: for key bursts, Python saves bridge/memory/screenshot proof if cheap, then pauses and saves after-pause screenshot + timer-stable proof before Codex inspects. Use at preview, deployment, first board, End Turn/reward/shop/map, mismatch/desync, popup. If screenshot stalls/fails, pause first and log. If screen/bridge/memory disagree, pause, log, trust no single source.

Memory file: keep durable log. Before stop/restart/block/patch, append to `run_notes/lightning_war_goal.md` or telemetry `summary.md`: attempt, timer, island/mission, burst, blocker, hypothesis, experiment/fix tried, result, next. Keep tried/worked/failed/next. Do not rely on chat memory.

Stop/restart: wrong setup, timer >=30:00, grid collapse, defeat, pilot death, mech HP/status/death, stale bridge, desync, route mismatch, cannot prove pause/timer stop, repeated UI blocker, dead pace. If blocked: capture evidence, pause/stop, patch only while verified paused/non-live, log, retry.
```
