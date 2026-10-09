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
```

`--replay` takes `--show N`, `--weapon ID`, `--trace RUN/MISSION/TURN`
(boards and effects of one turn), `--json FILE` (every mismatch) and
`--no-sync`.

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

Next up: stage 7 (the enemy phase).

Integration notes:

- A tile's occupant order is arrival order (`Pawn::arrival`). Boards loaded
  from recordings have no arrival history, so their shared tiles fall back to
  board-list order.
- Lua writes are applied when the script returns, so a script does not see
  its own writes (no shipped weapon script reads back what it wrote).
- Burrowers record their dive (`RulesContext::burrow_dives`) but stay on the
  board until stage 7 resolves the dive; the game lists them as gone.
- Multi-tile pawns (trains, dams) occupy only their main tile here.

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
- **Pilot level-ups.** A kill can level a pilot up mid-mission (+2 HP seen
  in the recordings); pilot XP is not in the bridge data.
