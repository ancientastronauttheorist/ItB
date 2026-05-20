# Adaptable Victory Rusting Hulks Retrospective

Date: 2026-05-19
Run: `20260519_200933_351`
Squad: Rusting Hulks
Difficulty: Easy
Target: Beat the game at the missing island length for Adaptable Victory

Outcome: **Adaptable Victory unlocked**. Achievement research and local logs showed that 3- and 4-island victories were already credited, leaving only the 2-island victory length. The run secured Detritus Disposal and Archive Inc., went directly to Volcanic Hive, won the final battle, and the in-game achievement toast appeared during the victory sequence. `python3 game_loop.py achievements --sync` confirmed Steam/client cache at `36/70`.

## Route

### Island 1: Detritus Disposal

- `Mission_BeltRandom`: secured.
- `Mission_AcidTank`: secured; accepted one dirty ordinary building/grid trade after confirming no objective failure.
- `Mission_Missiles`: secured.
- `Mission_AcidStorm`: secured with pod/core recovery.
- Corporate HQ / `Mission_BlobberBoss`: secured.

Shop after Detritus prioritized safe final-route power: reactor cores, grid power, Rocket move, and Aerial Bombs damage.

### Island 2: Archive Inc.

- Old Town / `Mission_Tides`: secured, Time Pod recovered, kill objective credited.
- Colonial Park / `Mission_Airstrike`: secured with both objectives credited.
- Storage Vaults / `Mission_Dam`: secured; accepted exact dirty consent `d34b52b82c77b9b4` for one ordinary F8 building/grid loss after confirming no objective failure.
- Excavation Site / `Mission_Survive`: secured; turn-1 threat-audit hold was reviewed, Reset Turn was not available, and the accepted threat did not damage grid/objectives.
- Corporate HQ / `Mission_JellyBoss`: secured cleanly, including Psion Abomination and Corporate Tower objectives.

After Archive, the Perfect Island reward and shop were used for survivability and final damage. The planner intentionally skipped a third Corporate Island.

### Volcanic Hive

- `Mission_Final`: won with grid at 7/7.
- `Mission_Final_Cave`: Renfield Bomb survived at 4/4, pylons remained intact, and final grid stayed 7/7.
- The final cave had non-blocking mech HP warnings and cave-danger triggers; each accepted solver plan moved mechs off danger while preserving bomb, pylons, and grid.

## Operational Notes

- Adaptable Victory is cumulative by victory length, not by squad. Once logs proved the 3- and 4-island lengths were already complete, the optimal target became a fast 2-island Easy win.
- The key strategic rule was "do not accidentally secure a third Corporate Island." After the second HQ, go straight to Volcanic Hive.
- Grid damage during corporate islands was acceptable for this achievement as long as the timeline survived; mission objective perfection was not required.
- On the final cave, `mission_ending` appeared repeatedly in save data while the bridge still had live final combat. Continue to follow the AGENTS final-island save-phase anomaly rule: trust fresh bridge only when it shows live final combat and active mechs, and never click through an `INVESTIGATE`/safety block.
