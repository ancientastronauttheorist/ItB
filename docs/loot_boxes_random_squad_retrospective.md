# Loot Boxes / Engineering Dropout Random Squad Retrospective

Run `20260531_114844_128` completed **Loot Boxes!** and **Engineering Dropout** on 2026-05-31 with Random Squad / Balanced Roll on Easy. The visible in-game achievement popups appeared after Pinnacle `Mission_BoomBots`; later Steam-cache checks no longer contradict the popups, and the global tracker advanced again when **Immortal** confirmed 51/70 on 2026-06-01.

## What Worked

- The route stayed alive long enough for pod RNG. The fifth recovered pod arrived on the fourth island, so abandoning after a missed Archive pod would have thrown away a winning line.
- Grid-first shops fit both targets. Buying Grid Power before cores kept the timeline alive, while not powering weapon modifications preserved Engineering Dropout eligibility.
- Pod counting through mission outcomes was reliable enough for route decisions: Detritus `Mission_AcidStorm` reached 1/5, R.S.T. `Mission_Volatile` reached 2/5, Archive `Mission_Mines` reached 3/5, Pinnacle `Mission_Reactivation` reached 4/5, and Pinnacle `Mission_BoomBots` reached 5/5.
- Fresh-read recovery after pod and click-miss desyncs preserved board certainty. The final `Mission_BoomBots` Teleporter click-miss was resolved from a fresh board with no active mechs before advancing.

## What Bit Us

- Loot Boxes is still RNG-heavy. Archive `Mission_Repair` failed a Time Pod, so the run needed two Pinnacle pod spawns instead of one.
- Several missions needed reviewed dirty lines. Ordinary grid/objective losses were acceptable for the target, but each consent stayed tied to an exact frontier and fresh board state.
- Pinnacle `Mission_Hacking` exposed player-team Cannon Bot aliases (`Snowtank1_Player` / `SnowtankAtk1_Player`). The fix added Python model coverage, Rust weapon mapping, known-types entries, and focused tests before the run continued.
- Steam sync was not available at closeout because credentials/client cache were not ready, so the README and checklist initially recorded these as observed in-game until later cache reconciliation.

## Carry Forward

For future Random Squad routes, treat **Loot Boxes!** and **Engineering Dropout** as complete. Keep the Loot Boxes playbook oriented around four islands, honest pod accounting, and grid-first survival. When a no-weapon-mod route is active, allow HP/move cores but leave weapon upgrades unpowered until the popup appears.
