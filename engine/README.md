# ITB engine

A clean-room C++ rules engine for Into the Breach, built to back a provably
optimal per-turn solver. The goal is "perfect turns": given the board a
player can see, find the best actions, simulating through the end of the
enemy phase. Ranking uses strict priority tiers: grid and buildings, then
mech survival, then objectives, then kills, then position.

The behavior comes from reading the game (the unstripped Linux build
21601364 in Ghidra, plus the shipped Lua). This directory contains only
original code and written rules. Game files, decompiler output and Ghidra
projects stay local and are never committed.

## Build and test

```bash
cmake -S engine -B engine/build -G Ninja
cmake --build engine/build
engine/build/itb_tests
```

Dependencies are fetched and pinned by hash: Lua 5.1.5 (the game's Lua
version), doctest and nlohmann/json.

Some tests run the game's own scripts. By default they look for the local
copy at `.local_decompile/builds/linux_21601364`; set `ITB_GAME_DIR` to use
another install, i.e. any directory that contains `scripts/scripts.lua`.
Without a game install, those tests warn and skip.

## Tools

```bash
engine/build/itb_inspect recordings/<run>/m07_turn_01_solve_input.json  # render a recorded board
engine/build/itb_inspect --pawns                                        # every pawn definition
engine/build/itb_inspect --scripts                                      # script load report
engine/build/itb_inspect --corpus recordings                            # load all recorded boards
engine/build/itb_inspect --weapons recordings                           # run weapon Lua on recorded boards
engine/build/itb_inspect --replay recordings                            # replay recorded actions vs the game
engine/build/itb_inspect --replay recordings --turns                    # whole turns, through the enemy phase
engine/build/itb_inspect --score recordings/<run>/m07_turn_01_solve_input.json  # score a recorded plan
```

`--replay` takes `--show N`, `--weapon ID`, `--trace RUN/MISSION/TURN`
(boards and effects of one turn), `--json FILE` (every mismatch) and
`--no-sync`. With `--turns` it replays each recorded turn whose plan it can
follow to the end, runs the enemy phase and compares with the game's board
at the start of the next turn (see "Validating the enemy phase").

## How game data is loaded

`GameData::load` runs the game's scripts in Lua 5.1, in the same
`GetScripts()` order the game uses. It supplies:

- the constants and value classes the binary binds natively (`Point`,
  `SpaceDamage`, `SkillEffect`, the list types), with luabind's rules;
- inert stubs for the remaining native functions the scripts call while
  loading (UI classes only).

The stubs are discovered automatically and reported, and the load verifies
that no stub shadows a Lua definition. Pawn definitions are read with normal
Lua inheritance. That covers every `AddPawn` entry plus every global table
derived from `Pawn`: 232 definitions in build 21601364.

## Status

Done so far (build order from the decompile):

- **Stage 1: core state and data.**
   - `core.hpp`: constants and A1–H8 notation.
   - `board.hpp`: tiles, pawns, and the pawn-list order that `Board::AddPawn`
     produces.
   - `game_data.hpp`: all pawn definitions, animation definitions and tuning
     values, read from the game's scripts.
   - `recording.hpp`: all 469 recorded boards load.
- **Stage 2: per-tile damage and status rules** (`tile_rules.hpp`).
   - The game's ordered `DamageSpace` steps in all three modes (weapon,
     push/bump, and the explosion mode corpse explosions use).
   - Pawn damage: shields, frozen, turn shield, armor and ACID.
   - Terrain, buildings and grid, cracks, items/mines.
   - Fire, smoke, acid and freeze interactions, terrain dangers, and the
     game's per-frame tile and pawn rules, either one frame at a time for the
     executor (skipping busy pawns) or until the board stops changing.
   - Grid Defense resists are a chance node: the caller resolves each roll, and
     every roll is logged. Pushes, spawns and Lua scripts are recorded for the
     later stages.
- **Stage 5: movement** (`movement.hpp`).
   - Pathing profiles, move budget and pilot move skills.
   - The game's reachability search and its weighted A* walk path (float32,
     (f, x, y) tie-break).
   - Walks, leaps, charges, teleports and burrows. With a stage 2 context,
     Injured goes through the stage 2 health change and the tile a move ends
     on is settled.
   - Every first move the old bot executed in a recording is reachable here:
     `itb_inspect --moves recordings`.
- **Stages 3 and 4: pushes, deaths and the SkillEffect executor**
  (`executor.hpp`, `timing.hpp`).
   - A frame-exact simulation of how the game resolves an effect: the six
     phases of the game's frame, an integer frame clock at a fixed frame rate,
     and every timer replayed in the game's float32 arithmetic. Frames where
     nothing can happen are skipped.
   - `Board::ApplyEffect` and the stacked-effect queue (FULL/PROJ/positive
     delays), projectiles, artillery, lasers, melee lunges, walks, leaps,
     charges, teleports and burrows.
   - Pushes and bumps with the game's same-frame ordering, dying bodies that
     block for half their death animation, death effects (ACID pools, Fast
     Decay, Lua hooks), corpse explosions, psion leaders and body removal.
   - Boost and Vek Hormones are baked in when an effect is computed.
   - Outcomes that hinge on two events within one frame are reported as
     timing-sensitive; Grid Defense rolls and spider-egg picks are logged as
     chance nodes.
- **Stage 6: the Lua host** (`lua_host.hpp`).
   - Runs the game's own weapon scripts (`GetTargetArea`, `GetSkillEffect`,
     queued Vek attacks, two-click weapons) and death effects on an engine
     Board, as the accuracy reference for C++ ports.
   - Native bindings follow luabind's rules: exact-arity overloads, strict
     argument types, aliasing `SpaceDamage&` / field references, one shared
     instance metatable (so `tostring(p)` and pawn `==` raise, as in game).
   - `random_int`, `random_bool` and `math.random` share a glibc `rand()`
     clone. Live seeds are hidden, so seeded results (e.g. the Large Goo
     split) are one sample of a random outcome.
   - Board queries read the engine Board directly; mutating bindings are
     reported (`LuaWrite`), not applied.
   - All 559 weapon ids run on the test boards without Lua errors, and
     every mech weapon and queued Vek attack in the recordings runs cleanly:
     `itb_inspect --weapons recordings`.

- **Stage 6 integration: shots end to end** (`engine.hpp`).
   - `Engine::move / fire_weapon / repair / fire_queued` run the game's
     own skill: Lua target area and `GetSkillEffect` (two-click weapons
     through `TranslateFirstClick`, `GetSecondTargetArea`,
     `GetFinalEffect`), `PrepareEffect` and `CheckAlterations`, the
     executor, then the `Pawn::FireWeapon` bookkeeping.
   - `sScript`s and `GetDeathEffect` run in the same Lua host against the
     board as it is at that frame; their writes (`Board:AddEffect`,
     `SetTerrain`, `Pawn:SetFrozen`, `Game:ModifyPowerGrid`, ...) are
     applied, the rest reported. Death effects that draw random numbers
     are logged as chance nodes.
- **Replay validation** (`itb_inspect --replay recordings`).
   - Replays every recorded player action from the board the old bot
     solved, and compares each move and attack with what the game did: the
     old bot's prediction plus the differences its verifier recorded, on
     exactly the fields that verifier compared. Results are split by how
     the bridge executed the action (native `FireWeapon`, `AddEffect`, or
     the bridge's own emulation) and by whether the old simulator was right.
   - Known recording artefacts are labelled, not counted as engine errors:
     multi-tile pawns, the old simulator's `active`, unrecorded weapon
     upgrades (a powered variant reproduces the game exactly), the bridge's
     SKIP behaviour.

- **Stage 7: the enemy phase** (`enemy_phase.hpp`, `environment.hpp`).
   - `Engine::end_turn(board, TurnContext)` runs End Turn up to the end of
     the enemy's spawns, in the game's order: Pawn::EndTurn on player pawns
     (Networked Shielding off), webs released, the six status-tick phases
     (one pawn per idle step, fresh list per phase, UpdateLeaders after each),
     environment steps, queued shooters (first in list order, re-aimed from
     the current tile, smoke/death/ice/water cancel), then the victory check,
     the mission's enemy NextTurn and the spawn cursor (blocked spawns take a
     push-mode hit and keep their marker; spawns on water/chasm are dropped).
     Every step resolves to idle on one frame clock; mission per-frame hooks
     (UpdateMission) run at every simulated frame. It stops before AI
     planning. `Engine::play_turn` runs the player's actions first.
   - `PhaseResult`: events, every chance node (Grid Defense, environment
     orders and choices, Lua death-effect randomness, spider eggs, mission
     picks), timing flags, Lua diagnostics, spawns of unknown type, and
     `exact = false` when the recorded data does not pin the result down.
   - Environments sit behind `Environment` (the mission's LiveEnvironment
     plus its combat hooks), dispatched on `mission_id`; a Lua-backed
     implementation can replace the native ones once the bridge exports the
     mission instance (spec stage 7 section 4). Table below.
   - The Soldier psion's +1 is tracked per pawn (`Pawn::health_bonus`):
     pawns that appear while it lives get it, pawns another psion does not
     affect keep a stale one. The Psion Tyrant reaches every player-team pawn.
   - Recordings: the mission data stage 7 reads (`Recording::mission`) and
     AE pilot level-up skills (Thick Skin, Technician).

- **Stage 8: the turn score** (`score.hpp`, `objectives.hpp`).
   - Strict tiers: grid and buildings, mechs, mission objectives, kills,
     position (see "Turn score" below).
   - Every shipped mission's objectives and the nine bonus objectives, in the
     game's reward units, from the recorded mission fields
     (`MissionData::objectives`).
   - `itb_inspect --score` scores a recorded plan; `--replay --turns` checks
     the objective counters against the game.

### Environments and mission hooks

"Exact" means: reproduced from what today's recordings contain. Newer bridge
fields (`environment_tides_index`, `environment_wind_dir`,
`mission_final_volcano`, `mission_final_cave`, `mission_hacking_*_id`) are
used when present.

| mission (env) | native behaviour | from recorded data |
|---|---|---|
| Mission_Airstrike (Env_Airstrike) | plane, then DAMAGE_DEATH on the 5-tile cross | exact (centre = the mark with 4 marked neighbours) |
| Mission_Lightning (Env_Lightning) | 4 strikes, DAMAGE_DEATH, one per step | strike order is hidden RNG: chance node `EnvOrder` over the k! orders of occupied strikes (empty strikes commute) |
| Mission_Crack (Env_Seismic) | 3 path tiles become chasms, in path order | exact when the path direction follows from last turn's chasm or the board edge; else chance node (2 orders, only if 2+ strikes are occupied) |
| Mission_Cataclysm (Env_Cataclysm) | column collapses top to bottom, 0.2 s per tile, buildings spared | exact (column from the marks; no marks = nothing can change) |
| Mission_Tides (Env_Tides) | row Index floods, building shadows, mountains DAMAGE_DEATH first | exact (row from the marks or the recorded index) |
| Mission_Terratide (Env_Terratide) | row 7-Index smoked from the bottom, no shadow | exact |
| Mission_SnowStorm (Env_SnowStorm) | 3x3 block frozen in one frame | exact (`environment_freeze`) |
| Mission_Wind (Env_RandomWind) | two columns pushed from the downwind edge, 0.2 s after occupied rows | exact with `environment_wind_dir`; old recordings: chance node `EnvChoice` (Down/Up) + EnvInexact |
| Mission_Belt / BeltRandom (Env_Belt) | belts push downstream first, 0.2 s after occupied belts | exact unless chains feed each other or a belt breaks mid-phase (EnvInexact: `Belts` order / CheckBelts quirk) |
| Mission_Final (Env_Volcano) | rocks: fire artillery DAMAGE_DEATH; lava: tile to lava; super-volcano repaired | exact with `mission_final_volcano`; old: mode and order from the tile pattern (EnvInexact for a single tile) |
| Mission_Final_Cave (Env_Final) | rocks drop (DAMAGE_DEATH, ground), tentacles (DAMAGE_DEATH, lava); bomb re-drop | exact with `mission_final_cave`; old: phase from the turn number (EnvInexact), phase-2 order a chance node; bomb drop a chance node `MissionRandom` |
| Mission_AcidStorm | every pawn ACID every frame while the generator lives | exact |
| Mission_Shields | new pawns shielded; generator death drops every shield | assumes every recorded pawn already had its shield (`ShieldedUnits` not recorded) |
| Mission_Hacking | facility death turns the bot into Snowtank1_Player | exact with ids; old recordings infer the bot (EnvInexact if several) |
| Mission_Dam | dam death floods two columns, 0.3 s per row | exact |
| Mission_Train / Armored_Train | train fires after every Vek; wreck replaces a dead train | queued move inferred (bridge omits team-1 shots); the rear tile is not modelled |
| Mission_Satellite | queued launch: DAMAGE_DEATH around, rocket flies away; NextTurn powering | exact with `queued_launch` |
| Mission_Volatile | last enemy retreats | exact with `is_infinite_spawn` |
| Mission_Reactivation | NextTurn thaws 2 random frozen enemies | chance node `MissionRandom` over the pairs |
| anything else with marks | none | `EnvUnsupported` (NanoStorm, Sandstorm, LandChange are unshipped) |

Spawn types are hidden (decided when queued, not shown): spawns without a
type in `TurnContext::spawn_types` emerge without a pawn
(`PhaseResult::emerged_unknown`). The bridge reports spawns in scan order,
not queue order; when that can matter (a blocked spawn among several) the
result says so (EnvInexact).

### Validating the enemy phase

`itb_inspect --replay recordings --turns` (corpus of 469 recorded turns):
324 turns have a plan the per-action replay follows to its end; 231 of them
have a trustworthy next-turn board (the board read when the next player turn
began, `m*_turn_<t+1>_solve_input.json`, or the `post_enemy` summary when that
board was read after the next turn had begun). 77 final turns have neither,
9 have captures that disagree on grid power.

Between the end of the spawns (where the engine stops) and that capture the
game ran AI planning and movement. Differences that step explains are
classified, not counted: instant smoke on queued targets (Mosquitoes), pawns
created at planning (Digger walls, spider eggs, blobs, totems, hatching), ACID
pools picked up by AI moves, Vek stepping on mines, UpdateSpawning additions
(Holes, Factory, Spider boss, Acid). So are recording artefacts: lava the old
bridge reported as water, pilot level-ups, and the Storm Generator upgrade
(the bridge reports `Passive_Electric` without `_A`). Hidden choices and
Grid Defense rolls are tried as branches; emerged spawn types are taken from
the next board.

Turns whose player steps all matched the game: 217, of which 148 exact
(68.2%) and 68 more with only explained differences (99.5%); the one left is
a post_enemy-only comparison (building HP total off by 1, grid power
matching). Turns that needed a mid-turn sync: 14, 64.3%.

### Turn score (stage 8)

`score_turn(before, after, ctx, phase)` (`score.hpp`) compares the board at
the start of the player's turn with the board after the enemy phase. Tiers
are strict and compared lexicographically; the search takes the worst case
over chance outcomes, the score judges one concrete outcome.

1. **Grid and buildings.** Grid power, then structure HP over building
   tiles, both as net changes. Unpopulated and objective buildings count; a
   destroyed building (rubble, or water for a building on water) has left
   the sum with all its HP. A grid gain counts for the player (none happens
   mid-turn in the shipped missions).
2. **Mechs.** Mechs alive, then mech HP, over the mechs on the board at the
   start, both net: a repair offsets damage and a revived corpse counts +1
   (the game's own `Board:GetMechDamage`, which BONUS_MECHS reads, is max HP
   minus current HP). A mech fallen into a chasm is lost with its HP.
3. **Objectives** (`objectives.hpp`): stars failed this turn, then progress.
4. **Kills.** Enemies killed, then enemy HP removed (net, so psion
   regeneration counts against the player). Enemies are team-6 pawns that
   are not neutral: Vek and enemy bots alike (both threaten buildings the
   same way); neutral team-6 pawns are mission props (hacked building, storm
   and shield generators, acid vats, minefield bots) scored as objectives.
   Only enemies alive at the start count, so this turn's spawns are not
   scored; kills by the enemy phase itself (fire, other Vek, environments)
   count like the player's. A retreat (minor flag set, HP 0) is not a kill.
5. **Position** (`position_terms`), a tie-break on the end board only:
   -3 per mech on fire (not fire-immune), -2 per mech with ACID, -2 per
   frozen mech, -1 per mech on smoke, -2 per mech at 1 HP; -1 per (enemy,
   adjacent building) pair (-2 for an objective building) and per enemy next
   to a player-team non-mech unit; +1 per enemy on fire or frozen. One pass
   over the pawns. Spawn tiles are left out: a blocked spawn stays queued and
   hurts its blocker again next turn, so occupying one is not a clear gain.

Pawn identity: engine uids of removed pawns can be handed out again within a
turn (new pawns take one more than the largest uid still on the board), so a
pawn on `after` is the same pawn only if its type matches and it did not
emerge from a spawn this phase (`same_pawn`).

**Objective units.** A *star* is the game's reward unit: each objective's
`Objective(text, value)` reputation, power or asset reward (every bonus
objective is 1). `ObjectivesFailed` is stars lost for good this turn: latched
failures when they happen, end-of-mission checks on the turn the mission
ends (`PhaseResult::mission_ended`; without a phase, `turn >= total_turns`).
Objectives are weighted by their stars, not equally: that is how the game
pays them. `ObjectiveProgress` is progress toward stars not yet earned, in
`kStar` = 840 units per star (lcm 1..8, so "1 of 5 kills" is exact); it can
be negative (fires put out, bots thawed). Time pods are not in the game's
objective list but are weighted as 1 star: lost when broken, secured when a
player unit picks one up.

| objective | failed (stars) | progress | data | exact |
|---|---|---|---|---|
| time pod | broken: 1 | collected: 1 star | tiles | yes |
| BONUS_ASSET (AssetLoc) | building damaged (`IsDamaged`): 1 | - | `objective_name` Str_* | yes |
| Mission_Critical: Solar/Wind/Power/Factory | each building damaged: 1 | - | `objective_name` Mission_* | yes |
| BONUS_KILL_FIVE | end: KilledVek < target | kills toward the target | `mission_kill_target`, `mission_kills_done` | yes |
| BONUS_PACIFIST | KilledVek crosses the limit | - | `mission_kill_limit`, kills | yes |
| BONUS_GRID | grid damage since deployment reaches 3 | - | PowerStart: turn-1 grid (later turns: this turn only) | turn 1 |
| BONUS_MECHS | end: mech damage >= 4 | (tier 2) | board | yes |
| BONUS_BLOCK | end: BlockedSpawns < 3 | blocked spawns (`SpawnBlocked`) | BlockedSpawns not exported | no |
| BONUS_DEBRIS | end: an egg sack left | sack destroyed: 1/2 | BonusDebris pawns | yes |
| BONUS_SELFDAMAGE | end: a mech infected | mite removed: 1/3 | `infected` | yes |
| BONUS_KILL | end: an enemy left | - | board | yes |
| Tanks, Civilians, Bomb, BotDefense (2 units) | each unit dies: 1 | - | pawn types | yes |
| Artillery, Filler, Volatile (no kill; a retreat is fine), Final_Cave bomb | dies: 1 | - | pawn types | yes |
| Train / Armored_Train (2) | stopped: 1; wreck dies: 1 | - | pawn types | yes |
| Satellite (2) | rocket destroyed: 1 | launched: 1 star | pawn types | yes |
| Dam, Shields, AcidStorm, Hacking tower, bosses | end: target alive | destroyed: 1 star | pawn types (`Mission_XBoss` -> `XBoss*`, Jelly_Boss) | yes |
| Hacking bot | bot dies (not its player-team swap): 1 | - | `mission_hacking_bot_id` or the shielded Cannon Bot | with ids |
| Disposal | unit dies: 1; end: mountains left: 1 | mountains destroyed | board | yes |
| Terraform | unit dies: 1; end: grass left: 1 | grass turned to sand | grass zone not exported | no |
| Force | end: Mountains < 2 | mountains destroyed (EVENT_MOUNTAIN_DESTROYED) | `mission_mountains_destroyed` | yes |
| AcidTank (2) | end: 2 - stars(AcidKills) | acid kills (1st: 1 star, 4th: 2) | `mission_kills_done` = AcidKills | yes |
| Barrels (2) | end: each vat left: 1 | vat destroyed: 1 star | AcidVat pawns | yes |
| BoomBots (2) | end: 2 - stars(destroyed) | bots destroyed (2: 1 star, 4: 2) | `_Boom` pawns, 4 placed | yes |
| ForestFire (2) | end: 2 - stars(fires) | fires on the board (8: 2 stars) | tiles | yes |
| Repair | end: RepairPickups < 3 | platforms used by player units | `repair_platforms_used` | yes |
| FreezeBldg | end: thawed < 5 | buildings thawed or destroyed | `freeze_building_tiles` | with tiles |
| FreezeBots (2) | bot dies: 1; end: bot not frozen: 1 | bot frozen: 1 star | pawn types | yes |
| BlobBoss | end: dead blobs < 5 | blobs killed | dead blobs estimated from the living | no |
| Missiles (2) | - | - | Missile_Unit shots not modelled | no |
| Final (survive) | - (no reward) | - | - | - |

Bonus objectives come from the bridge's `bonus_objective_ids` when exported
(51 of 469 recorded boards); otherwise from what other fields reveal: a kill
target (KILL_FIVE; on Mission_AcidTank it is the mission's own goal), a kill
limit (PACIFIST), an Str_* building (ASSET), egg sacks (DEBRIS), infected
mechs (SELFDAMAGE). GRID, MECHS and BLOCK cannot be inferred; GRID and MECHS
only add a threshold to what tiers 1 and 2 already rank.

Native counters follow the decompile: `Pawn::ProcessDeath` raises
EVENT_ENEMY_KILLED for every team-6 non-minor death (bots included, any
killer) and EVENT_ACID_DESTROYED for team-6 deaths with ACID; Mission.KilledVek
only counts while KILL_FIVE or PACIFIST is active (Mission:BaseUpdate).

Validation (`itb_inspect --replay recordings --turns`, the 216 replayed
turns with a trustworthy next board, 15 more against post_enemy): the
engine's kill count matches the next turn's `mission_kills_done` on all 19
turns where the game counts kills; repair platforms 4/4; objective buildings
standing 231/231; pods 231/231; infected mechs 216/216. Every scored failure
(8: a Cannon Bot, an Archive tank, three Volatile Vek, two trains stopped,
a pod) happened in game too.
`itb_inspect --score <recording>` prints one recorded plan's score, every
objective line and the position terms beside the game's outcome.

Integration notes:

- A tile's occupant order is arrival order (`Pawn::arrival`). Boards loaded
  from recordings have no arrival history, so their shared tiles fall back to
  board-list order.
- Lua writes are applied when the script returns, so a script does not see
  its own writes (no shipped weapon script reads back what it wrote).
- Burrowers record their dive (`RulesContext::burrow_dives`) but stay on the
  board during the player phase; in the enemy phase they leave it
  (`Pawn::pos` invalid, previous tile in `movement.prev_pos`) until the AI
  resurfaces them.
- `Engine::end_turn` leaves `Board::player_phase` false and does not apply
  the next player turn's start (Zoltan shields, Opener/Closer, last-turn
  spawn clearing): score those as next-turn context.
- Multi-tile pawns (trains, dams) occupy only their main tile here. In game
  a Vek attack on a train's rear tile kills it (seen in the recordings).

### Open questions for live-game testing

- **Vek attack order.** The decompile says board-list order, which is
  insertion order within the player and non-player groups. Recordings made
  before 2026-06-23 only have a bot-computed uid order, and just 3 later
  boards carry the game's real order. Confirm against the live game,
  especially for re-added pawns.
- **Injured and walking.** AE Injured costs 1 HP per tile change. The code
  suggests every step of a walk counts (and undoing the move costs 1 more);
  check in game.
- **Point plus number.** What `Point + number` means natively. It's only
  seen in UI layout code so far.
- **Estimated durations.** Teleport, burrow, walk-step, air-strike and
  dropper animation lengths are estimates (`timing.hpp`); they only shift
  when things happen. Measure them in game.
- **Frame rate.** Some outcomes depend on the frame rate (the executor flags
  them). Check what frame rate and speed level the game really runs at.
- **Mechs standing in fire (Mission_BurnbugBoss).** Recorded mechs on a
  burning tile were not set on fire, although `CheckAcidFire` runs every
  frame for idle occupants. Find what prevents it.
- **Spider eggs webbing newcomers.** Mechs that moved next to a `WebbEgg1`
  were webbed in game. The decompiled web check releases webs to empty
  tiles, so how the egg re-webs is not understood yet.
- **Stage 8 objectives.** The bridge could export Mission.BlockedSpawns,
  PowerStart, the Terraform grass zone and Missile_Unit's shots left; until
  then BONUS_BLOCK, BONUS_GRID after turn 1, Terraform and Missiles are
  approximate. That a pod still intact at mission end is recovered is
  assumed, not checked against the game.
- **Pilot level-ups.** A kill can level a pilot up mid-mission (+2 HP seen
  in the recordings); pilot XP is not in the bridge data.
- **Enemy phase (stage 7).**
   - Spawn types and queue order are hidden; the bridge could forward the
     save's `spawns` / `spawn_ids` / `spawn_points`.
   - Passive upgrades: six recorded turns only match with the Storm
     Generator's +1, which the bridge does not report.
   - The train's queued move is assumed every turn (the bridge omits team-1
     queued shots); Mission_Shields' `ShieldedUnits` is assumed complete.
   - Lightning's realised strike order (spec stage 7 section 4.4 ledger)
     would confirm the order chance node.
   - A pawn killed by `SetMutation` at the quiescent frame (psion death)
     might leave the board idle for one frame (spec stage 7 O1).
   - Nine turns' `post_enemy` summaries disagree with the next turn's board
     on grid power: check when each is captured.
