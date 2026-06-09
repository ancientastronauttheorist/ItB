# Lightning War Memory-Aware Goal Prompt

Paste the block below into `/goal`. Prompt length target: under 4000 chars.

```markdown
Goal: Earn Into the Breach "Lightning War": Blitzkrieg squad, Easy, clear the first 2 Corporate Islands before the in-game timer reaches 30:00. Do not need full victory, perfect islands, bonus objectives, pods, reputation, or clean grid, only survival through island 2 HQ and achievement proof.

Use AGENTS.md rules. Combat bridge/Rust solver is source of truth. Run session-touching game_loop commands one at a time. No blind live-clock thinking: pause first, or let Python runner act.

Speed plan: Easy Blitzkrieg. Prefer Archive + R.S.T. when available. Favor fast missions: Train, Tidal Wave, Cataclysm, Sandstorm, 4-turn maps. Avoid Pinnacle when alternatives exist and avoid slow RNG such as Burrowers, Tumblebugs, Blast Psion, Smoldering Psion, long environmental animations. Target about 3 min/mission. Island 1 should finish <15:00; abandon/restart if island 2 pace cannot finish <30:00.

Tactics: ignore optional objectives if they cost time. Preserve grid above 0, pilots alive, mechs not destroyed at mission end. Use Lightning Mech for fast multi-kills; do not overthink perfect chains. Use Boulder Mech aggressively to block spawns and reduce enemy-turn time. Hook/Boulder set up whip kills only when obvious. Buy Grid Power first if below max; if grid is safe/full, leave shops fast. Building Chain is good if powered cheaply. Strong pilots: Kazaaakpleth on Hook for offense or Camila on Lightning to ignore web/smoke; otherwise use current best pilot.

Timer/pause findings from findings.md: pause menu open freezes visible timer; closed makes visible timer advance. Use this to prove whether thinking is free. Preferred probe:
`python scripts/itb_timer_memory_probe.py watch-context --pid <pid> --sample-seconds 5`
`timer_state=stable` => likely pause menu open. `moving` => likely closed/live clock. Pause bytes and pointer paths are process-local hints only, not durable. Old `Breach.exe+0x4bc7e8` became stale after restart. Fresh heap pause hits can help but must be rediscovered. Do not trust old f32 timer pointer paths after restart; f32 scans can find stale copies. Visible timer strings in memory are the practical pause detector.

Use pause menu deliberately. Pause to route/patch/think. Python scancode Esc can toggle the menu when normal Computer Use key injection fails. Reset Turn is allowed; timer rolls back to turn start, so reset is not automatically fatal.

Memory findings discipline: raw strings and GameData copies can be stale. Mission-select strings like "Excavation Site", "Old Town", and `iBattleRegion` are useful, but rank by freshness/current seed/current squad/current region; raw presence is not proof. For grid/pilot memory, rank current-looking GameData blocks and gate skills by level: skill1 active only level>=1, skill2 only level>=2. Skill IDs: 0 HP, 1 Move, 2 Grid DEF, 3 Reactor, 8 Skilled, etc. Grid Defense = base 15 on Easy/Normal/Hard + overflow + active Grid DEF perks. Buy grid before other shop items when low.

Live run loop: verify Blitzkrieg/Easy/timer enabled/speed settings; start Archive/R.S.T. route if possible; choose fastest provable missions; deploy quickly; `auto_turn`/Lightning runner solves and executes; click End Turn only from emitted safe plan; after each mission clear panels quickly; leave island/shop fast; continue until island 2 HQ completion and achievement popup or `achievements --sync`.

Stop/restart if: wrong squad/difficulty/AE setup, timer >=30:00 before achievement, grid collapse/defeat, pilot death, mech destroyed at mission end, stale bridge/desync uncertainty, unpausable live state requiring Codex thought, repeated UI blocker, or route pace dead. If blocked, capture concise evidence, pause/stop, patch only from verified pause/non-live, then retry.
```
