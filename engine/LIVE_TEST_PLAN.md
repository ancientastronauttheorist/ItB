# Live test plan

Tests for the engine's open questions (README, "Open questions for
live-game testing") and for the bridge extension, run against the game on
this Mac. Each test builds a board with the bridge's `SCENARIO` command,
lets the engine predict it from the bridge's own dump, plays it, and diffs
the game with the prediction. `scripts/live_validate.py` does all of that
except clicking End Turn.

Coordinates are the bridge's `(x, y)`; the engine prints A1-H8
(column `H - y`, row `8 - x`, so `(3,5)` is `C5`).

## How to run the session

1. **Build** (once): `cmake -S engine -B engine/build -G Ninja && cmake --build engine/build`.
   Use the main checkout so `itb_inspect` finds the game scripts, or set
   `ITB_GAME_DIR` to `.local_decompile/builds/linux_21601364`.
2. **Install the bridge**: `bash scripts/install_modloader.sh`, then start
   (or restart) Into the Breach.
3. **Debug flag**: `touch /tmp/itb_bridge_debug`. It enables `SCENARIO` and
   `FIRE`, the per-frame phase log and the enemy-phase captures. Remove it
   (`rm /tmp/itb_bridge_debug`) before letting the bot play normally again.
4. **Use a throwaway run.** Scenarios remove and create pawns, rewrite
   terrain and queue spawns in the current mission, and the game saves it.
   Easy difficulty, any squad. Do not run `auto_turn` while testing.
5. **Smoke test** (below): `python3 scripts/live_validate.py check`.
6. Start a mission, deploy, and at a player turn run
   `python3 scripts/live_validate.py run <scenario>`. When it says so, click
   End Turn (fullscreen 1360x768: `(128, 89)`). It waits for the enemy
   phase and prints the diff, the phase log and what to look at. Everything
   is saved in `.local_runs/live_validation/<time>_<scenario>/`
   (`before.json`, `prediction.txt/.json`, `game_capture.json`,
   `game_prespawn.json`, `diff.txt`, `phase_log.txt`).
7. Most scenarios need **a mission without an environment** (`check`
   prints `env_class`; it should be `Env_Null`) and a turn that is not the
   last. `lightning_order` and `train_rear` need their missions. One
   scenario per turn; after the enemy phase you are at the next player turn
   and can run the next one (the old board is cleared by the next
   scenario).
8. `python3 scripts/live_validate.py predict <scenario>` gives the engine's
   answer offline on a synthetic copy of the board (all ground, Rift
   Walkers); the predictions quoted below come from it.

Bridge commands added (all ack in `/tmp/itb_ack.txt`):

| command | what it does |
|---|---|
| `SCENARIO <json>` / `SCENARIO @<file>` | builds a board (debug only; format in `ITBX.scenario_apply`, src/bridge/modloader.lua); the ack is a JSON report (created uids, errors, snapshot file) |
| `SCENARIO_RESET` | forgets the scenario's queued-shot and spawn-queue ledger |
| `SNAPSHOT [label]` | dumps the state now, also to `/tmp/itb_snapshot_<label>.json` |
| `MOVE_NATIVE uid x y` | moves like a player click: the Move skill through `Pawn:FireWeapon(p, 0)`, else `Pawn:Move`, else `SetSpace`; the ack names the method |
| `FIRE uid slot x y` | `Pawn:FireWeapon` with the game's slot numbers (0 = Move; debug only) |
| `PHASE_LOG [clear]` | writes the per-mission phase log to `/tmp/itb_phase_log.json` |
| `DEBUG_STATUS` | flag file, extension version, active scenario |

Captures written with the debug flag: `/tmp/itb_state_enemy_prespawn.json`
(`Mission:BaseNextTurn` for team 6: after the Vek attacks and the
environment, before the spawns) and `/tmp/itb_state_enemy_postspawn.json`
(first `Mission:PlanEnvironment` of the enemy turn: after the spawns, before
the AI moves). The engine's `end_turn` stops at the second one.

## 0. Bridge smoke test and new fields

`python3 scripts/live_validate.py check` (any screen with a mission; also
during deployment). Expect:

- the game starts normally; `/tmp/itb_bridge.log` has
  `ITB Bot Bridge started`; the old bot's `python3 game_loop.py read`
  still works (one call is enough);
- `bridge_ext_version 1`, `bridge_errors []`. Any entry names the export
  that failed; the rest of the dump is unaffected. Report each one;
- `mission_state`: `key`/`native_key` match the mission (`Mission<key>`),
  `class_chain[0]` is the mission id, `env_class_chain[0]` the environment
  (Env_Null for most missions), `dump_truncated false`;
- `save_source` is `saveData.lua` or `undoSave.lua` (the one matching the
  board and newest);
- `spawn_queue`: one entry per spawn marker, `matches markers: True`. Write
  down the types; at the next turn the Vek that emerged on those tiles must
  have those types (the order matters only when one is blocked);
- per mech: `weapons` lists every equipped slot with its upgrade suffix
  and passives (compare with the mech panels: a powered Titan Fist upgrade
  shows as `Prime_Punchmech_A/_B`), `(unpowered)` for weapons without their
  core, limited weapons as `uses n/m`; `pilot ... xp` matches the pilot's
  XP bar; `moved False` at turn start, `True` after a move;
- trains / rockets: `queued (non-enemy)` on Mission_Train and
  Mission_Satellite, and their uids last in `attack_order_all`;
- during deployment (`turn 0`): `drop_zone` equals the yellow tiles
  (`drop_zone_source`: `zone`, or `default` = x 1-3, y 1-6 when
  the map has no deployment zone), and `deployment_zone` is present;
- BONUS_BLOCK missions: `blocked_spawns` counts spawns blocked so far;
  every mission: `power_start` = the grid when the mission was deployed;
- Mission_Missiles: `mission_missiles.shots_used`; Mission_Terraform:
  `terraform_grass_tiles`.

Limited uses: fire a squad mech's limited weapon (if the squad has one) and
run `check` again: its `uses` drops by 1 (`calibrated`). Otherwise run
`limited_uses` (section 10).

## 1. Vek attack order (board-list order)

Decompile: queued shots fire in pawn-list order; new pawns are appended to
their list group. Three scenarios on the same board: a Firefly at (1,3)
aimed right (its shot stops at the first pawn, the Hornet at (3,3), HP 1),
the Hornet aimed at mech 0 at (3,4).

`run vek_order` (Firefly created first). Engine:

```
event shot fired Firefly1#104 E6: FireflyAtk1
event shot cancelled Hornet1#105
Hornet1#105 E5: removed
```
mech 0 keeps its HP.

`run vek_order_reversed` (Hornet first). Engine:
```
event shot fired Hornet1#104 D5: HornetAtk1
event shot fired Firefly1#105 E6: FireflyAtk1
PunchMech#0 D5 hp 3 -> 2
Hornet1#104 E5: removed
```

`run vek_order_readd` (created as in `vek_order`, then the Firefly is
removed and added back: `{"ref": 4, "readd": true}`). The decompile says a
re-added pawn goes to the end of its group, so this plays like the
reversed order:
```
event shot fired Hornet1#105 D5: HornetAtk1
event shot fired Firefly1#104 E6: FireflyAtk1
PunchMech#0 D5 hp 3 -> 2
```

Observe: mech 0's HP, the snapshot's `attack_order`, and the phase log's
`selected` entries (the order the game selected shooters). If the game
disagrees, the native order is something else (e.g. uid order): note
`attack_order` and the `selected` sequence.

## 2. Mechs standing in fire (Mission_BurnbugBoss)

Recorded mechs on burning tiles in Mission_BurnbugBoss were not set on
fire; the engine sets them on fire (CheckAcidFire every frame for idle
occupants). The first live session found that the old MOVE (SetSpace) does
not ignite on arrival either.

`run fire_under_mech`: mech 0 stands at (3,3) and its tile is set on fire
afterwards (`tiles_after`); mech 1 is put on the burning (5,3) with
SetSpace; mech 2 walks (1,5) -> (1,3) onto fire with `MOVE_NATIVE`.
Engine (all three ignite; each loses 1 in the fire tick):
```
action #2 move E7: ok
event status tick PunchMech#0 (1): fire -1
event status tick TankMech#1 (1): fire -1
event status tick ArtiMech#2 (1): fire -1
PunchMech#0 fire off -> on      (E5, hp -1)
TankMech#1 fire off -> on       (E3, hp -1)
ArtiMech#2 moved C7 -> E7, fire off -> on, hp -1
```
Observe: the `before.json` snapshot (after SCENARIO, before the move): are
mechs 0 and 1 on fire? Then the move's ack names the method
(`FireWeapon[0]` expected) and the state after it: is mech 2 on fire?
Then the HP after the enemy phase. Also play an actual Mission_BurnbugBoss
turn with the debug flag on and run `python3 scripts/live_validate.py log`:
the `tile`/`hp` entries show when the boss sets tiles on fire and whether
the mechs on them start burning.

## 3. Spider eggs webbing mechs

Recorded: mechs that moved next to a `WebbEgg1` were webbed; the decompiled
web check releases webs to empty tiles, so the mechanism is unknown.

`run web_egg`: an egg at (3,3) with its hatch queued (as the AI does),
mech 1 placed next to it at (3,4), mech 0 walks (1,3) -> (2,3) with
`MOVE_NATIVE`. Engine (no webs; the egg hatches in the enemy phase):
```
action #0 move E6: ok
event shot fired WebbEgg1#104 E5: WebeggHatch1
WebbEgg1#104 E5: removed
new Spiderling1#105 at E5 hp 1
```
Observe `web` / `grappled` on mechs 0 and 1 after SCENARIO and after the
move. If webbed: by placement, by the walk, or only after the egg's hatch
was queued (rerun without `queue` on the egg to separate them).

## 4. Lightning strike order

Env_Lightning strikes its marks in an order drawn at random each step
(`random_removal`); the engine enumerates the orders as a chance node.

`run lightning_order` on Mission_Lightning at a player turn with at least
two marks: an explosive psion (`Jelly_Explode1`) on the first mark, a
Scorpion on the second, mech 0 next to the Scorpion. Engine (two outcomes):
```
== outcome 1 [EnvOrder 1/2]     psion struck first: no explosion
Jelly_Explode1 removed, Scorpion1 removed
== outcome 2 [EnvOrder 2/2]     Scorpion struck first: it explodes
PunchMech#0 hp 3 -> 2, Jelly_Explode1 removed, Scorpion1 removed
```
Observe: `env_strike_log` in the capture (one entry per step, with the
struck tile in `current_attack`) and mech 0's HP; the diff names the
outcome that matches, and it must be the order in the log. Repeat on other
turns: each run shows one order.

## 5. A Vek hitting the train's rear tile

The train occupies two tiles (main + `ExtraSpaces` (0,1)); the engine only
places it on its main tile. Recordings show a Vek attack on the rear tile
killing the train.

`run train_rear` on Mission_Train (or Armored Train) while the train runs:
enemies cleared, a Hornet placed left of the rear tile and aimed at it.
Engine on the synthetic board (train at (4,4), rear (4,5)): the sting hits
nothing, then the train moves on:
```
event shot fired Hornet1#101 C4: HornetAtk1
event shot fired Train_Pawn#60 E4: Train_Move
Train_Pawn#60 moved D4 -> F4
```
Observe: does the train take the hit (and die at 1 HP, leaving its wreck)?
If the tile left of the rear is blocked, edit `dx` in the scenario.

## 6. Tri-Rocket timing knife-edge

Ranged_Crack: three pushing rockets 0.15 s apart, far tile first. The far
Scorpion (2,0) at 1 HP dies; the middle one's push up lands about 0.55 s
later, against a ~0.56 s "dying body still blocks" threshold. Blocked: it
stays at (2,1) with 1 HP; not blocked: it moves to (2,0) with 2 HP.

`run trirocket_timing`: a temporary player-team PunchMech pawn at (2,5) is
given Ranged_Crack (`weapons_add`) and fires it with `FIRE uid 2 2 1`
(native slot 2). Engine at 60 fps (not flagged timing-sensitive here):
```
action #106 Ranged_Crack at G6: ok
Scorpion1#104 H6: removed
Scorpion1#105 G6 hp 3 -> 1        (blocked)
```
Observe the middle Scorpion's tile and HP. Run it three times; if the game
varies, the outcome depends on frame timing at this machine's frame rate.

## 7. Injured: HP per step

AE Injured costs 1 HP per tile change; the code suggests every step of a
walk counts (and undoing costs 1 more).

`run injured_walk`: both mechs get Injured (0-damage `iInjure` hit); mech 0
walks 2 tiles with `MOVE_NATIVE`, mech 1 is moved 2 tiles with the old
`MOVE` (SetSpace in fast mode). Engine (it walks both; 1 HP per step):
```
PunchMech#0 moved G7 -> E7, hp 3 -> 1
TankMech#1 moved G2 -> E2, hp 3 -> 1
```
Observe the HP after each move and the phase log's `hp` entries (one drop
per step, or one per move). If HP does not change at all, Injured did not
take: check the SCENARIO report. Undo is not available through the bridge:
test it by hand (move a mech with the mouse, undo, compare HP).

## 8. Psion death and the idle frame (stage 7 O1)

When a Soldier psion dies, `SetMutation` kills Vek that lived only on its
+1. Question: does the board look idle for one frame before that death
animation makes it busy (so the next shot could start)?

`run psion_idle_frame`: Firefly A (0,2, 4 HP under the psion) shoots the
psion (2,2, 1 HP); the Scorpion at (4,2) has 1 HP of a psion-raised 4 and
is aimed at mech 0 (4,3); Firefly B (6,2) shoots left along the row.
Engine:
```
event shot fired Firefly1#104 F7: FireflyAtk1
event shot fired Firefly1#107 F3: FireflyAtk1
event shot cancelled Scorpion1#106
Firefly1#104 F8 hp 4 -> 2      (-1 psion gone, -1 from B: B's shot passes the dead Scorpion)
Jelly_Health1#105 removed, Scorpion1#106 removed
Firefly1#107 F2 hp 4 -> 3
```
Observe: mech 0 keeps its HP (the Scorpion never stings); where B's shot
lands (Firefly A's HP); and in the phase log, the frames of the psion's
`hp`/`gone`, the Scorpion's `hp 1 -> 0`, the `busy` changes and B's
`selected`. A `busy -> 0` frame between the psion's death and the
Scorpion's death answers O1 (yes).

## 9. When are enemy-phase states captured? (post_enemy)

Nine recorded `post_enemy` summaries disagree with the next turn on grid
power. The bridge reads `grid_power` from the save, which the game writes
at turn boundaries.

`run capture_timing`: a Firefly at (3,5) shoots up at a 1-HP building at
(3,2); a spawn is queued at (5,5). Engine:
```
event shot fired Firefly1#104 D5: FireflyAtk1
event spawn emerged Scorpion1#105 C3: Scorpion1
tile F5 building -> rubble
grid 7 -> 6
```
Observe: in `game_prespawn.json` and `game_capture.json` the building is
rubble but `grid_power` is still the turn-start value; at the next player
turn (`check`) it is 1 lower (or unchanged if Grid Defense resisted: the
building would then be intact). If you also run `python3 game_loop.py read`
during the enemy phase, note which grid its post_enemy summary shows.

## 10. Spawn queue and limited uses

`run spawn_queue`: two queued spawns, the second blocked by mech 0. Engine
(full information: types and queue order from the bridge):
```
spawn queue (queue order): C3 Scorpion1 E3 Firefly1
event spawn emerged Scorpion1#3 C3: Scorpion1
event spawn blocked PunchMech#0 E3
PunchMech#0 E3 hp 3 -> 2
```
Observe: the Scorpion emerges at (5,5); mech 0 loses 1; at the next turn
`spawn_queue` still holds the Firefly at (5,3).

`run limited_uses`: a temporary PunchMech pawn given Brute_Heavyrocket
(Limited 1) fires it (`FIRE uid 2 2 5`). Engine: the Scorpion at (2,5)
dies. Observe `shots_remaining` of that pawn: 2 before, 1 after (this
settles how GetShotsRemaining counts); then `FIRE uid 2 2 5` again by hand
returns `ret=0`.

## 11. Native moves vs SetSpace

From the first session: the old `MOVE` (SetSpace in fast mode) skips
arrival effects. In every run above, compare the ack of `MOVE_NATIVE`
(method `FireWeapon[0]` expected) and the unit's `moved` flag in the next
dump (`True`, `moved_source turn_start`). If `MOVE_NATIVE` falls back to
`Move` or `SetSpace`, its ack says why.

## What to bring back

For each run, the folder under `.local_runs/live_validation/` (the diff,
captures and phase log), plus any `bridge_errors` and anything the bridge
log (`/tmp/itb_bridge.log`) says around the run.

## Risks

- The extension is checked offline only (Lua 5.1 compile, a strict mock of
  every binding it calls, the binding table of the Linux build). A native
  call can still behave differently in game: every new export is pcall'd
  and reported in `bridge_errors`, and the old dump does not depend on it.
- The wraps of `Mission:BaseNextTurn`, `ApplyEnvironmentEffect` and
  `PlanEnvironment` call the original once and return its result;
  if the game misbehaves in the enemy phase, remove the debug flag first
  (the captures and the per-frame log are debug only), then reinstall the
  previous bridge.
- `FireWeapon` on a scenario-created Vek must accept the target (it must be
  in the weapon's target area); the report lists `FireWeapon returned 0`
  otherwise.
- `grid_power` in captures and after SCENARIO is the save's turn-start
  value: compare building HP mid-turn and grid at the next player turn.
- Scenario-created pawns get the current psion's mutation; give explicit
  HP where it matters (as `psion_idle_frame` does).
