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

Stage 1 of the build order (core state and data) is done:

- `core.hpp`: points, directions, terrain, team and leader constants, plus
  A1–H8 notation.
- `board.hpp`: tiles, pawns, and the board's pawn-list order. That order is
  the regrouping `Board::AddPawn` performs, which drives Vek attack order.
- `game_data.hpp`: pawn definitions read from the game's scripts.
- `recording.hpp`: boards loaded from the bridge recordings. All 469
  recorded boards load, and every unit type resolves.

Next up: stage 2, the per-tile damage and status rules (`ApplySpaceDamage`).

Stage 5 (movement) is in `movement.hpp`: pathing profiles, move budget and
pilot move skills, the game's reachability search and its weighted A* walk
path (float32, (f, x, y) tie-break), and executing walks, leaps, teleports and
burrows. Arrival hazards are left to stage 2: callers settle the returned
tile.

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
