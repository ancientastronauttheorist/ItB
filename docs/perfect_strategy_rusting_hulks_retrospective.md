# Perfect Strategy Rusting Hulks Retrospective

Date: 2026-05-19
Run: `20260518_215903_654`
Squad: Rusting Hulks
Difficulty: Easy
Island: Archive Inc.

Outcome: **Perfect Strategy unlocked**. The in-game achievement pop-up appeared immediately after the Archive Inc. Perfect Island reward flow, and `python3 game_loop.py achievements --sync` confirmed `Perfect Strategy` complete with Steam/client cache at `34/70 (+1 fresh)`.

## Route

The final cumulative Perfect Island reward came from a fast Island 1 Rusting Hulks grind:

- Artifact Vaults: protected the Coal Plant and secured the region.
- Old Town: defended the Armored Train, collected the Time Pod, and opened a Reactor Core.
- Research Center: protected the Coal Plant and preserved the Volatile Vek.
- Accord Repository: protected Emergency Batteries under Tidal Waves and stayed below the mech-damage cap.
- Corporate HQ: destroyed the Centipede Leader and protected the Corporate Tower.

The Perfect Island reward was collected as `+2 Grid`, raising Grid Defense and completing the cumulative achievement count.

## Key Live-Loop Note

Research Center final turn safety-blocked even though a clean line existed. The salvaging line was:

- RocketMech moved `C5 -> B5` and fired Rocket Artillery at `E5`, killing the E5 Hornet.
- PulseMech stayed on `C3` and used Repulse, pushing the protected Volatile Vek from `C4 -> C5` without damage.
- JetMech moved `G4 -> F3` and used Aerial Bombs toward `F5`, smoking/damaging the F4 Hornet so its E4 attack was canceled.

This preserved the Volatile Vek, Coal Plant, grid, and buildings. The normal click route missed the Rocket move, so the line was executed through the bridge writer one action at a time with fresh `game_loop.py read` verification after each action.

## Follow-Ups

- Add a regression board for the Research Center final-turn clean line so the Rust solver can find it instead of safety-blocking.
- Investigate why Aerial Bombs / Repulse / Rocket coordination was absent from the candidate frontier on that board.
- Keep Perfect Strategy farming notes biased toward first-island Easy Rusting Hulks until another squad proves more stable.
