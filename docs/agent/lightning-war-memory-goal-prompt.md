# Lightning War Memory-Aware Goal Prompt

Paste the block below into `/goal`. Prompt length target: under 4000 chars.

```text
Goal: unlock "Lightning War". Blitzkrieg. Easy. Finish first 2 Corporate Islands before game timer 30:00. Default AE/Base Content OFF unless setup verifies otherwise. No win/perfect/bonuses/pods/rep/clean grid needed. Island 2 HQ survived + Steam proof.

Law: AGENTS.md. One session-touching `game_loop.py` command at a time. Fresh bridge/Rust are combat truth; stale/desync/uncertain combat means stop. Codex thinks only while paused/non-live. Python owns live clock.

Pause/timer: pause up = think, pause down = act. Cycle: plan paused -> Python unpauses/runs burst -> Python pauses -> stable proof -> Codex inspects. Never blind Esc if already paused; use `ensure_pause` or visible proof. If focus/input bad, Python SendInput/scancode Esc may pause. Best proof: screenshot shows pause menu + unchanged timer. If classifier says `island_map_or_unknown` but screenshot shows pause menu + stable timer, trust screenshot. Probe if needed:
`python scripts/itb_timer_memory_probe.py watch-context --pid <pid> --sample-seconds 5`
`stable` = paused-ish, `moving` = live clock. Pointer paths/old pause bytes/f32 timer are hints only.

Windows UI: trust calibrated Windows controls; never scaled macOS coords. First corp island may need two clicks: highlight then confirm. Mission preview Start may be preview board/Start area. End Turn uses emitted/calibrated safe plan only. No stacked blind clicks; screenshot after surprising UI.

Bridge/menu truth: bridge can be stale on menus/maps; stale menu bridge is not fatal if screen proof is clear. Fresh bridge ACK/read mandatory at deployment/combat. Combat bridge/screen/memory disagreement => pause/log/stop.

Fast loop: verify Blitzkrieg/Easy/AE-off/timer/speed -> Start -> select+confirm island -> clear intro -> pause proof -> inspect/scored preview -> validate mission/objectives -> bridge deploy -> confirm -> Lightning segment/auto_turn burst -> pause/result proof -> clear rewards/shop/map fast -> repeat. Runner must park paused.

Route: use repo scorer/evidence, but never start without visible preview validation. Prefer Archive/R.S.T. and proven train/plain/low-friction/4-turn missions. Avoid Satellite, Mines, Bad Repairs, Power Generator, Forest Fire, slow enemies/animations. Tidal can be fast but risky. Avoid preview => back out/restart if no fast alternative.

Pace gates: target ~3 min start-to-start. First deployment after ~3:00 is restart unless route proof is exceptional. First mission complete after ~6:00 is usually restart. Island 1 must finish <15:00. Be harsher than "maybe recover."

Tactics: speed over nice. Ignore optional objectives if slow. Keep grid >0, pilots alive, no mech HP/status/death. Lightning kills clusters. Boulder blocks spawns. Hook/Boulder set whip kills only when obvious. Buy Grid Power first when below max; if full/safe, leave shop fast.

Memory/staleness: raw strings/GameData can be stale. Rank by freshness/current seed/squad/region. Raw presence is not proof. Pilot skills need level gate: skill1 active level>=1, skill2 active level>=2. Skill IDs: 0 HP, 1 Move, 2 Grid DEF, 3 Reactor, 8 Skilled.

Evidence sandwich: key bursts save cheap bridge/memory/screenshot proof, then pause and save after-pause screenshot + timer-stable proof before Codex inspects. Use at setup, island select, preview, deployment, first board, End Turn/reward/shop/map, mismatch/desync, popup. If screenshot stalls/fails, pause first.

Memory file: before stop/restart/block/patch, append to `run_notes/lightning_war_goal.md` or telemetry `summary.md`: attempt, timer, island/mission, burst, blocker, hypothesis, fix/experiment, result, next.

Stop/restart: wrong setup, timer >=30:00, grid collapse, defeat, pilot death, mech HP/status/death, stale combat bridge, desync, route mismatch, cannot prove pause/timer stop, repeated UI blocker, dead pace. Patch only while verified paused/non-live. After island 2 HQ/popup run `python3 game_loop.py achievements --sync`; done only when `unlocked_list` has `Lightning War`.
```
