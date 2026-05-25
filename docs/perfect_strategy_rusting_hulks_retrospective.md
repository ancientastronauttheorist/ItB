# Perfect Strategy Rusting Hulks Retrospective

Date: 2026-05-19
Runs: `20260518_215903_654` and `20260519_133059_179`
Squad: Rusting Hulks
Difficulty: Easy
Final island: Pinnacle Robotics

Outcome: **Perfect Strategy unlocked**. Archive Inc. in run `20260518_215903_654` brought effective progress to 9/10 Perfect Island rewards. The final reward came from a fresh Pinnacle Robotics clear in run `20260519_133059_179`; `python3 game_loop.py achievements --sync` confirmed `Perfect Strategy` complete with Steam/client cache at `34/70 (+1 fresh)`.

## Route

### 9/10 Setup: Archive Inc.

- Artifact Vaults: protected the Coal Plant and secured the region.
- Old Town: defended the Armored Train, collected the Time Pod, and opened a Reactor Core.
- Research Center: protected the Coal Plant and preserved the Volatile Vek.
- Accord Repository: protected Emergency Batteries under Tidal Waves and stayed below the mech-damage cap.
- Corporate HQ: destroyed the Centipede Leader and protected the Corporate Tower.

The Archive Perfect Island reward was collected as `+2 Grid`, bringing the cumulative count to the doorstep. The timeline was then abandoned for a fast final Island 1 grind.

### 10/10 Unlock: Pinnacle Robotics

Run `20260519_133059_179` used Rusting Hulks on Easy with Ralph Karlsson as time traveler:

- Cold Storage: clean objective clear, Time Pod recovered, Reactor Core collected.
- The Tundra: `Kill 4 or fewer Enemies` and `Protect the Coal Plant` completed cleanly.
- District Z-1001 / `Mission_Factory`: Robot Factories defended; RocketMech's pilot was KIA, but the objective stayed complete and the mech continued under AI.
- Shielded Vaults / `Mission_FreezeBldg`: `Break 5 buildings out of the ice` and `Kill at least 5 Enemies` completed. The run accepted reviewed non-objective grid/building damage only after objective counters stayed reachable.
- Corporate HQ / `Mission_BurnbugBoss`: Gastropod Leader destroyed and Corporate Tower protected.

The final Perfect Island reward was collected as `+2 Grid`, topping the grid back to 7/7 and triggering the Steam/client-cache confirmation for `Perfect Strategy`.

## Key Live-Loop Note

Two live-loop issues mattered during the final push.

### Archive Research Center

- RocketMech moved `C5 -> B5` and fired Rocket Artillery at `E5`, killing the E5 Hornet.
- PulseMech stayed on `C3` and used Repulse, pushing the protected Volatile Vek from `C4 -> C5` without damage.
- JetMech moved `G4 -> F3` and used Aerial Bombs toward `F5`, smoking/damaging the F4 Hornet so its E4 attack was canceled.

This preserved the Volatile Vek, Coal Plant, grid, and buildings. The normal click route missed the Rocket move, so the line was executed through the bridge writer one action at a time with fresh `game_loop.py read` verification after each action.

### Pinnacle Shielded Vaults

`Mission_FreezeBldg` exposed a simulator gap: Aerial Bombs transit over a frozen thaw-objective building can thaw it, reduce building HP, and defer the resulting grid loss to enemy-turn settle. The live miss was patched as simulator v150 and covered by a focused Rust unit test before the post-enemy block was resolved. After that, the mission was completed with the thaw counter at 5/5 and the kill counter at 6/5.

This run also reinforced that no-failed-objective achievements need explicit counter safety, not just generic grid/building safety. `freeze_buildings_thawed`, `mission_kill_target`, and similar counters must be visible in plan safety or manually verified before the final End Turn.

## Follow-Ups

- Add a regression board for the Research Center final-turn clean line so the Rust solver can find it instead of safety-blocking.
- Promote the Shielded Vaults v150 capture into replay/corpus coverage, not only the focused Rust unit test.
- The follow-on **There is No Try** push succeeded in run `20260519_154655_297`; see `docs/there_is_no_try_rusting_hulks_retrospective.md`.
