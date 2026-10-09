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
```

## How game data is loaded

`GameData::load` runs the game's scripts in Lua 5.1, in the same
`GetScripts()` order the game uses. It supplies:

- the constants the binary binds natively;
- a working `Point`;
- inert stubs for native functions the scripts call while loading.

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

Next up: stage 6 (weapons: the Lua `GetSkillEffect`, `GetDeathEffect` and
`sScript` hooks the executor takes).

Integration notes:

- A tile's occupant order is arrival order (`Pawn::arrival`). Boards loaded
  from recordings have no arrival history, so their shared tiles fall back to
  board-list order.

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
