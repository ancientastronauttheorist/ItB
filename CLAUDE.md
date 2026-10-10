# Into the Breach solver

The achievement bot finished its job: all 70 achievements, earned autonomously
by 2026-07-09. The project's goal now is a **provably optimal per-turn
solver** built on an exact model of the game. Its rules come from reading the
game itself (the unstripped Linux build in Ghidra, plus the shipped Lua). The
same solver drives the live bot.

## Layout

| Path | What |
|---|---|
| `engine/` | The C++20 rules engine and perfect-turn solver. **Read `engine/README.md` first.** |
| `engine/python/` | pybind11 module `itb_engine` used by the live bot |
| `src/`, `game_loop.py` | The live bot (Python): bridge IPC, the game loop, verification, the strategy layer |
| `src/bridge/modloader.lua` | The in-game Lua bridge (installed into the game's app bundle) |
| `rust_solver/` | Legacy Rust solver, kept as the bot's fallback |
| `recordings/` | Recorded boards, plans and outcomes from past runs (the engine's validation corpus) |
| `docs/agent/` | Live-bot manuals: `live-runbook.md`, `safety-gates.md`, `solver-reference.md`, `achievement-playbook.md` |
| `.local_decompile/` | Git-ignored workbench: game builds, Ghidra exports, specs in `notes/stage*_spec.md` |

## Hard rules

- **Clean room, public repo.** Never commit game files, decompiled code,
  Ghidra output or anything copied from `.local_decompile/`. Engine code is
  written from behavioural specs in our own words; addresses and function names
  are fine to cite.
- **Don't run the legacy Python test suite (`tests/`) on the desktop** without
  asking first. Several tests launch the game and trigger macOS permission
  prompts. Safe to run: `engine/build/itb_tests`, `python3 -m unittest
  tests.test_cpp_solver`, `scripts/validate_cpp_solver.py`.
- **The engine is the rules authority.** Older notes (`data/ref_game_mechanics.md`,
  the docs/agent mechanics sections) are empirical and partly wrong; for example,
  pushing a unit into the board edge does nothing. When they disagree, trust
  the engine and its specs.
- Engine changes keep the existing checks green: unit tests, plus `itb_inspect
  --corpus/--moves/--weapons/--replay/--replay --turns` on `recordings/`. Speed
  work must not change any result.

## Build and test

```bash
cmake -S engine -B engine/build -G Ninja -DITB_BUILD_PYTHON=ON -DPython_EXECUTABLE="$(command -v python3)"
cmake --build engine/build
engine/build/itb_tests                                # needs the game's scripts: ITB_GAME_DIR or the local copy
engine/build/itb_inspect --replay recordings --turns  # engine vs real game outcomes
engine/build/itb_inspect --solve <state.json> --time 30 --threads 8
python3 -m unittest tests.test_cpp_solver             # bot adapter + module only
```

Rust fallback, after editing `rust_solver/src/*.rs`:
`cd rust_solver && maturin build --release && pip3 install --user --force-reinstall target/wheels/itb_solver-*.whl`

## Live play

- **Bridge:** `scripts/install_modloader.sh` copies `src/bridge/modloader.lua`
  into the game (Terminal needs macOS *App Management* permission). Restart
  the game afterwards. The bridge writes `/tmp/itb_state.json` and takes
  commands through `/tmp/itb_cmd.txt` (`src/bridge/protocol.py`,
  `writer.py`: MOVE / ATTACK / REPAIR / SKIP / END_TURN / DEPLOY).
- **Engine live play:** `python3 scripts/live_play.py status | deploy | turn |
  end-turn | mission` (engine/README.md "Live play"). Solves with the C++
  engine (`engine/build/itb_live`), executes each sub-action through the
  bridge, checks it against the prediction, re-solves on a mismatch; `mission`
  stops at the first anomaly. `--dry-run` never acts. Runs are archived in
  `recordings/live/<time>/`.
- **Old bot combat:** `python3 game_loop.py auto_turn --time-limit N` reads the board,
  solves with the C++ engine (`ITB_SOLVER=cpp`, the default; `rust` is the
  fallback), executes each sub-action, verifies it against the prediction and
  re-solves on a desync. Then end the turn. Full protocol and gates (research
  gate, INVESTIGATE, diagnosis loop) are in `docs/agent/live-runbook.md` and
  `safety-gates.md`.
- **Coordinates:** bridge `(x, y)` is the native board point; visual row
  = 8 − x, column = 'H' − y, so `(3, 5)` is C5. Talk in A1–H8.
- **UI navigation** (menus, deployment, rewards, shop, island map) is
  screenshot-driven. In fullscreen at 1360×768, tile `(x, y)` is at screen
  `(676 + 57·(x−y), 117 + 41·(x+y))` and End Turn is at `(128, 89)`.
- **Bridge data:** since the extension (fae1c5ef) it exports exact weapon ids
  (`weapons_exact`, `weapon_slots`), `moved`, the drop zone and mission state;
  `MOVE_NATIVE` moves like a click (`MOVE` teleports with `SetSpace` and skips
  arrival effects); `END_TURN` deactivates the mechs (no confirm dialog), but
  End Turn still needs a click on this build. Older bridges: give
  `live_play.py --loadout` (the save's `primary`/`secondary` plus `*_mod1/mod2`).

## Play preferences

- New runs: Easy, Advanced Edition on, Balanced Roll squad.
- Shop: buy Grid Power until it's full, then spend on what helps the run.
  Don't leave reputation unspent.
- The solver ranks turns by strict tiers, in this order: grid, buildings, mech
  losses, mech HP, objectives, kills, position. Chance (Grid Defense, Lightning
  order, death splits) is taken worst case. Don't override its plan by hand;
  if it looks wrong, that's an engine bug to investigate.
