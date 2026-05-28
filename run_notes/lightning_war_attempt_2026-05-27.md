# Lightning War Scout Attempt - 2026-05-27

Goal: Blitzkrieg, Easy, finish first two corporate islands under 30:00.

Operating rule: think only while paused. Unpause only for deployment confirm,
enemy settle, solver execution, End Turn, and reward/map clicks.

## Live Notes

- Start hypothesis: Archive + R.S.T. is best; prioritize Train, Tidal Wave,
  Cataclysm, Sandstorm, and avoid pod/dam/slow objective animations.
- Current lesson from previous run: Old Earth Park dam + pod flow cost too much
  time; do not take it unless forced.
- Extra-high thinking is okay while paused; low thinking should mostly help only
  if the agent accidentally reasons while the game clock is running.
- Restart overhead: abandoning a live timeline through UI adds a pilot carry-over
  screen. Keep Camila for Lightning Mech speed and web/smoke immunity.
- Setup verified Blitzkrieg/Easy. Extra content remains ON: useful for R.S.T.
  Cataclysm/Sandstorm, but it increases the number of slow mission rolls.
- Fresh run reached first island intro/menu at 0:38. Opening start/cutscene plus
  pause click costs around 38 seconds before any mission choice.
- Mistake: a blind click after Start selected Detritus instead of deliberately
  choosing Archive/R.S.T. Fix: after Start, wait for island-select state, inspect
  labels, then click Archive deliberately; do not click through empty map areas.
- Corrected route: deliberate Archive selection reached Archive intro paused at
  0:48. Initial island-select plus confirmation still costs about 20 seconds.
- First Archive route choice leaked too much live timer: mission inspection went
  from roughly 1:30 to 3:09 before the pause landed. Colonial Park showed
  Satellite Launches; Central Museums showed Artillery Support + Power
  Generator. For speed, inspect at most one alternative while paused or choose
  the first acceptable mission.
- Mission start UI lesson: clicking the province label/body can merely toggle
  or re-open the preview/dialogue. The large mission-preview board is the Start
  Mission hitbox. Use one deliberate preview-board click after choosing the
  mission.
- Deployment pause lesson: the combat gear is not available while placing
  mechs; use `deploy_recommended` immediately, then confirm. After confirm,
  the first pause should wait until the Player Turn banner clears, otherwise
  the bridge can still report `combat_enemy` with zero active mechs.
- Paused `auto_turn` is not viable: it can solve while the menu is open, but
  bridge execution stalls with a stale heartbeat because Lua stops ticking.
  Practical loop is pause for human/agent thinking, then unpause for a compact
  live `auto_turn` burst.
- Central Museums ended around 9:43, far over Lightning War pace. Combat was
  not the only issue: first mission start/preview/deployment/pause timing
  consumed about four minutes before turn 1, and the final dirty frontier review
  added another visible minute.
- Enemy-turn pause timing: pausing on the Player Turn banner leaves the bridge
  at `active_mechs=0`. Either wait until the banner is fully gone before
  pausing, or let `auto_turn` be the waiter when the next step is already
  execute.
- Final-turn safety frontier lesson: rank 49 preserved grid and building HP
  while risking only the optional objective; for Lightning War this is better
  than the top-ranked grid-loss line. Exact consent flow worked but cost time.
- Low-thinking implication: most lost time is UI/tool latency and process
  friction, not model reasoning while paused. Low thinking helps only if we use
  a precommitted route/play protocol and avoid live deliberation entirely.
- Second mission flow improved: after reward, clicked Continue, selected
  Colonial Park, clicked the visible Start Mission preview, used
  `deploy_recommended`, confirmed, then chained `auto_turn` immediately after
  each End Turn. Satellite mission finished around 14:20, roughly 4:20 from map
  start to reward despite being a 4-turn environmental mission with launches.
- Faster combat loop candidate: do not pause between every clean combat turn.
  Use pause for route choice, dirty/frontier review, shops/rewards, and
  unexpected states; otherwise click End Turn and immediately start the next
  `auto_turn` so the bridge handles the enemy/player transition.
- Forgotten Hills / Mines started around 15:21 after a no-comparison map pick.
  This map rolled mines plus a time pod. The first turn produced a spawn
  desync/fuzzy novelty from Rock Launcher, and by turn 4 it became a
  `RESEARCH_REQUIRED` stop sign. A Lightning War attempt should pre-clear
  research queues and avoid pod/mine routes when a cleaner mission is available.
- Attempt effectively dead at 20:18: still on first island mission 3 with a
  research gate active. Even with the faster clean-turn loop, the first-island
  opening mistakes and mission mix leave no realistic path to two islands under
  30:00.

## Next Attempt Protocol

- Before start: clear/review research queue, verify no pending behavior novelty
  can interrupt combat, and keep Options at timer on / fast enemy movement.
  New helper: `python3 game_loop.py lightning_preflight --set-bridge-fast`.
- Use `python3 game_loop.py lightning_attempt --time-limit 2` as the default
  post-route conductor: it handles bridge deployment, clicks the calibrated
  CONFIRM button, and chains combat through `lightning_loop`. It stops on
  route/reward/unknown screens instead of guessing. Use
  `python3 game_loop.py lightning_ui pause`, `... reward_continue`, or
  `... modal_understood` / `... panel_continue` for calibrated
  between-screen clicks.
- First island: select Archive deliberately, then choose the first acceptable
  fast/low-friction mission. Do not compare more than one alternative.
  Helper: `python3 island_select.py --lightning-war`, then after Archive
  `python3 island_select.py --lightning-war --completed archive`.
- Map UI: one region click, one preview-board Start Mission click, immediate
  `deploy_recommended`, confirm, then immediate `auto_turn`.
- Smoke test note: after HQ reward flow, promotion and Perfect Island panels
  can sit on top of an island map that the bridge already exposes. If
  `lightning_attempt --dry-run` returns `ROUTE_READY` while a visible panel is
  still open, clear the panel with `lightning_ui modal_understood` or
  `lightning_ui panel_continue` before trusting the route recommendation.
- Combat loop: `auto_turn --time-limit 2` is enough for simple Easy turns and
  saves solver clock. Prefer `python3 game_loop.py lightning_loop --time-limit 2`
  from clean player-turn combat so End Turn gets clicked locally and the next
  `auto_turn` waits through enemy animations. Pause only for dirty blocks,
  research gates, reward/shop/map routing, or unexpected visuals.
- Map helper: `python3 game_loop.py recommend_mission --routing lightning_war`
  favors Train, Tidal, Cataclysm/Seismic, and Sandstorm over reputation or
  fragile objectives.
- Dirty policy for Lightning War: prefer optional-objective loss over grid loss;
  never spend live time preserving pods, kill-count bonuses, or satellite-style
  bonuses unless the solver gets them for free.
- Archive opening options: Colonial Park = Satellite Launches, likely slow.
  Central Museums = Artillery Support + Power Generator, selected as lower
  complexity. Inspecting both nodes cost roughly 30 seconds (1:07 -> 1:30).
