# Quantum Entanglement Flame Behemoths Retrospective

Date: 2026-05-20
Run: `20260520_134643_900`
Squad: Flame Behemoths
Difficulty: Easy
Target: Teleport a unit 4 tiles away

Outcome: **Quantum Entanglement unlocked**. The live confirmation came after the Teleporter was fully upgraded to `Science_Swap_AB`. The decisive recorded solve was mission 14 turn 4:

`TeleMech, move B3->B5, fire Teleporter at F5`

From B5 to F5 is exactly four tiles along a cardinal row, satisfying the achievement without relying on diagonal targeting. The attack verify recorded only a non-blocking fire tile-status mismatch (`tile_status|Science_Swap_AB|attack`), so the upgraded Teleporter path executed and the achievement toast was observed. The 2026-05-20 Steam sync reconciled the checklist to 37/70.

## What Changed

- `Science_Swap_A/B/AB` must be explicit weapon IDs, not inferred from the base `Science_Swap` loadout.
- Save-backed effective weapon overlays matter. The Lua bridge can report the pawn's base SkillList while the save file contains the powered weapon variant.
- Bridge execution must fire the effective upgraded weapon ID. A base `Science_Swap` ACK can silently no-op at four-tile range.
- Upgraded Teleporter targeting is cardinal-line only. Diagonal targets such as the earlier C6-style attempts are invalid even when their Manhattan distance looks plausible.

## Route Notes

- The run targeted both **Quantum Entanglement** and **This is Fine**.
- Reactor-core routing mattered more than perfect objectives. Mission choices prioritized core rewards and high enemy density over perfect-island cleanliness.
- Earlier Flame Behemoths attempts exposed the two important blockers: diagonal Teleporter enumeration and save/loadout offset confusion. Fixing those made the final four-tile swap boring in the best possible way.

## Next Target

Keep Flame Behemoths pointed at **This is Fine**. Quantum no longer needs special weighting except as a regression guard for `Science_Swap_AB`; future Flame Behemoths scoring should favor simultaneous burning enemies, high-spawn missions, and lines that keep burning Vek alive long enough to count.
