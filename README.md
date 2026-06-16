# Into the Breach Achievement Bot

An autonomous bot that plays [Into the Breach](https://subsetgames.com/itb.html) on macOS and Windows, aiming to earn all 70 Steam achievements. Codex-style agents are the live control loop; Python + Rust handle state extraction, combat planning, and click synthesis; a Lua mod-loader bridge wires everything into the running game.

Status: **55 / 70 achievements Steam-cache confirmed** after **On the Backburner** unlocked on 2026-06-15 in Mist Eaters play. Steam offline mode or missing sync credentials can delay reconciliation: visible or in-game awards may not appear in `achievements --sync` until Steam goes online and Into the Breach restarts.

Recent unlocks: **On the Backburner** unlocked and Steam-cache synced on 2026-06-15 in Mist Eaters Easy run `20260615_172629_338`; the Thruster Mech used Reverse Thrusters on Detritus `Mission_Acid`, with A.C.I.D. doubling a two-tile dash into the required 4 damage. The run also prompted simulator v266-v268 support for Reverse Thrusters, Smoldering Shells occupied-smoke behavior, and Nanofilter Mending smoke healing. **Chronophobia** unlocked and Steam-cache synced on 2026-06-14 in Zenith Guard Easy run `20260613_234901_918` after leaving the third Corporate Island; the run destroyed every discovered Time Pod, including pod failures on Archive `Mission_Mines`, Pinnacle `Mission_Stasis`, and R.S.T. pod missions, using the new `--destroy-time-pods` solver policy. **Powered Blast** unlocked and Steam-cache synced on 2026-06-11 in Bombermechs Easy run `20260611_202233_019`; the solver spawned a Walking Bomb at C2, then Pierce Mech fired AP Cannon from D2 through the bomb to kill the Scarab at B2 on Archive `Mission_Artillery` turn 4. **Trick Shot** reconciled on 2026-06-02 after Steam was brought online; Steam recorded `Ach_Pinnacle_B_2` at 14:50:21 CDT, while local run evidence suggests the in-game Janus Cannon credit happened earlier during the offline Frozen Titans route. **Immortal** unlocked on 2026-06-01 in Hazardous Mechs Easy run `20260531_181444_169` after a four-corporate-island Detritus finale; the final Corporate HQ result showed Region Secured, both HQ bonus objectives checked, and all three mech portraits present before the Steam cache moved `Ach_Detritus_B_2` into achieved. **Loot Boxes!** and **Engineering Dropout** popped in-game on 2026-05-31 in Random Squad Easy run `20260531_114844_128`; the fifth recovered pod came from Pinnacle `Mission_BoomBots`, and the same no-weapon-modification route completed three Corporate Islands. **Class Specialist** unlocked on 2026-05-30 in Custom Squad Easy run `20260529_164303_219` with Combat Mech + Laser Mech + Aegis Mech after a two-island Windows victory; **Change the Odds** unlocked on 2026-05-27 in Random Squad Easy run `20260527_152006_916` after Archive HQ by buying Grid Defense to 30%; **Mech Specialist** and **Flight Specialist** unlocked on 2026-05-27 in Custom Squad Easy run `20260526_204256_831` with 3x Ice Mech after a two-island final victory; **Distant Friends** unlocked on 2026-05-26 in Frozen Titans Easy run `20260525_203546_657` after the hidden H2 beacon pickup on R.S.T. `Mission_Force`; **Hold the Line** unlocked on 2026-05-24 in Blitzkrieg Normal run `20260524_195401_412` after a manual four-block spawn cluster on Detritus Corporate HQ; **Healing** and **Overkill** reconciled on 2026-05-24 after the Hazardous Mechs Easy 4-island victory run `20260522_193613_471` and a Steam online/game restart; **Untouchable** popped in-game on 2026-05-22 after Frozen Titans Easy Archive run `20260522_133722_695`; **Unstable Ground** was confirmed by the 2026-05-21 sync during the Cataclysm run `20260521_120049_468`; **This is Fine** also reconciled in that sync after its 2026-05-21 Flame Behemoths Easy toast in run `20260520_174936_811`; **Quantum Entanglement** was confirmed by the 2026-05-20 sync after a four-tile `Science_Swap_AB` Teleporter line in Flame Behemoths run `20260520_134643_900`; **Adaptable Victory** was confirmed by the 2026-05-19 sync after the Rusting Hulks Easy 2-island victory run `20260519_200933_351`; **There is No Try** was confirmed earlier on 2026-05-19 after the Rusting Hulks Easy no-failed-objectives run `20260519_154655_297`; **Perfect Strategy** was confirmed earlier on 2026-05-19 after a Rusting Hulks Easy Pinnacle Perfect Island reward in run `20260519_133059_179`; **Ramming Speed**, **Chain Attack**, and **Squads Victory** were confirmed by the 2026-05-18 sync after the 2026-05-17 Blitzkrieg victory push; **Stormy Weather** and **Hard Victory** on 2026-05-16; **Get Over Here**, **Shield Mastery**, and **Glittering C-Beam** on 2026-05-10; **Trusted Equipment** on 2026-05-09; **Perfect Battle** on 2026-05-08; **Backup Batteries**, **Overpowered**, **Best of the Best**, and **I'm getting too old for this...** on 2026-05-07. See `TODO.md` for the checklist.

Current milestone: **On the Backburner** is closed and Steam-cache confirmed. The solver now has Mist Eaters support for Reverse Thrusters achievement scoring, Smoldering Shells smoke placement, and Nanofilter Mending healing, plus the Time Pod destruction policy for Chronophobia and Bombermechs support for Bomb Dispenser, Walking Bomb, and AP Cannon-through-bomb achievement scoring. Remaining cleanup can pivot to Blitzkrieg **Lightning War**, Cataclysm, the remaining Mist Eaters/Heat Sinkers/Arachnophiles targets, or the remaining Random target **Lucky Start**.

---

## How it works

The game runs natively. State flows out through a Lua mod hook that writes `itb_state.json`; commands flow back through `itb_cmd.txt`, ACKed via `itb_ack.txt`, with a heartbeat file to detect a hung bridge. The bridge directory is platform-specific: `/tmp` on macOS and `Documents/My Games/Into The Breach/itb_bridge` on Windows, unless `ITB_BRIDGE_DIR` overrides it. For UI screens the bridge can't drive (deployment, menus, shop, rewards, island map), the bot emits pixel-coordinate click plans and dispatches them via the `computer-use` MCP.

### Five-layer architecture

| Layer | Code | Role |
|---|---|---|
| 0 — Game loop | `game_loop.py` + `src/loop/` | Stateless CLI. Every invocation: load session -> compute -> save. The agent is the orchestrator. |
| 1 — State extraction | `src/bridge/` (primary), `src/capture/` (fallback save-file parser) | Bridge gives per-sub-action updates, targeted tiles, env hazards with kill flag, deployment zone. Save file only updates at turn boundaries. |
| 2 — Game state | `src/model/` | `Board`, `Unit`, `WeaponDef` - the solver's single source of truth. |
| 3 — Solver 2.0 | `rust_solver/` (`itb_solver` PyO3 extension) + thin Python wrappers in `src/solver/` | Rust is the only simulator and search engine. Python handles wrapping, audit breakdowns, verification, tuning, and research feedback. |
| 4 — Strategist | `src/strategy/`, `src/loop/commands.py`, `weights/active.json`, achievement metadata in `data/` | Picks run setup, mission priority, shop behavior, and `EvalWeights` for achievement hunting. Current default: Easy + Advanced Edition + achievement-aware named squad; Balanced Roll is reserved for solver-eval and random-squad targets. |

### Solver 2.0

Solver 2.0 is built around a stricter goal than "highest score this turn": avoid irreversible loss first, then optimize threats, kills, spawns, XP, and achievement shaping.

- **Rust is authoritative.** `rust_solver/` owns search, enemy simulation, player-weapon simulation, projection, scoring, and replay. `src/solver/simulate.py` has been deleted; `src/solver/solver.py` is a small dataclass/wrapper layer around `itb_solver`.
- **Candidate search is wider.** The loop asks Rust for top-K one-turn candidates and depth-2 beam chains (`solve_top_k`, `solve_beam`, `project_plan`) instead of trusting only the top raw-score plan.
- **Plan safety gates bad wins.** Every candidate is replayed and checked for irreversible losses: grid power, building HP, objective buildings, pods, mech deaths, and unsafe self-damage. The first clean candidate wins, even if it scored slightly lower.
- **Execution is closed-loop.** `auto_turn` executes move -> verify -> attack/repair -> verify through the bridge, re-solves after desyncs, and withholds End Turn on unexplained predicted-vs-actual grid drops.
- **Upgrades are first-class.** Achievement-critical variants such as `Science_Swap_AB` are represented in the save overlay, Rust weapon IDs, target enumeration, and bridge firing path, so the solver can see and execute upgraded weapon behavior rather than silently falling back to base loadouts.
- **Unknowns stop the bot.** The research gate blocks solving past uncatalogued pawns, terrain, weapons, and screens. Recent live-loop catalog work includes Digger, Wall, Centipede, Wind Torrent, AE psion/boss behavior, and Bombermechs Walking Bomb deployables.
- **Failures feed the next version.** `recordings/failure_db.jsonl`, the fuzzy detector, the diagnosis queue, weapon override staging, regression boards, and `EvalWeights` tuning turn live mistakes into repeatable fixes.

### Self-healing research loop

When `read` encounters an unknown pawn type, terrain, weapon, or UI screen, it returns `RESEARCH_REQUIRED`. The loop then:

1. `research_next` emits an MCP capture plan (crop regions + Vision prompts).
2. The agent dispatches the plan, runs Vision on each crop, submits JSON via `research_submit`.
3. If confidence is low, community notes (Steam / Reddit) are fetched and attached via `research_attach_community`.
4. Results land in `data/known_types.json`, `data/weapon_overrides_staged.jsonl`, and `data/weapon_penalty_log.json`.

See `docs/self_healing_loop_design.md` for the four-phase design (Instrumentation → Passive Response → Research Pipeline → Active Response).

### Failure database and auto-tuning

Every desync between predicted and actual board writes a record to `recordings/failure_db.jsonl`. Four commands consume it:

- `analyze` — pattern breakdowns by trigger, tier, severity, squad, island.
- `tune` — random search + coordinate refinement on `EvalWeights`; objective is `mean_fixed_score − 100 × failure_count`.
- `validate` — replays all recorded boards under two weight versions; gates deployment on ≤20% regression rate and zero critical building-loss regressions.
- `diagnose_next` — drains one queued desync investigation, producing a rule match or an agent prompt for Rust-side simulator fixes.

Tuned weights land in `weights/v{NNN}_{date}.json`; the deployed copy is `weights/active.json`.

---

## Setup

### Prerequisites

- macOS or Windows. macOS uses Quartz and `/tmp`; Windows uses Win32 window detection, PIL `ImageGrab`, and the profile-local `itb_bridge` directory.
- Python 3.9+
- Rust toolchain
- `maturin` (`pip install maturin`)
- Into the Breach on Steam (App ID `590380`), with [ITB-ModLoader](https://github.com/itb-community/ITB-ModLoader) installed

### Install the Lua bridge

```bash
bash scripts/install_modloader.sh   # macOS: copies src/bridge/modloader.lua into the Steam app bundle
# then restart Into the Breach
```

Re-run after any edit to `src/bridge/modloader.lua`. On Windows, install the same Lua file into the ITB-ModLoader location used by the game, then restart Into the Breach. Set `ITB_SAVE_DIR` or `ITB_BRIDGE_DIR` only when using nonstandard save or bridge locations.

### Build the Rust solver

```bash
cd rust_solver
maturin build --release
pip3 install --user --force-reinstall target/wheels/itb_solver-0.1.0-cp39-cp39-macosx_11_0_arm64.whl
```

Re-run after any edit to `rust_solver/src/*.rs`. The wheel filename is
platform- and Python-version-specific; use the wheel produced under
`rust_solver/target/wheels/` on Windows.

### Git hooks

```bash
bash scripts/install-hooks.sh
```

### Secrets

`.env` (gitignored) holds `STEAM_API_KEY` and `STEAM_ID` for achievement queries and local checklist sync.

---

## Quick start

On Windows PowerShell, prefer `python -X utf8 game_loop.py ...` for the same
commands shown below.

```bash
# Start a new run
python3 game_loop.py achievements --sync
python3 game_loop.py recommend_squad --tags achievement
python3 game_loop.py new_run auto --difficulty 0 --tags achievement
# On the new-game screen: Easy, Advanced Edition ON, select the recommended squad, then Start
#
# Solver stress-test / random-squad mode:
python3 game_loop.py new_run auto --mode solver_eval --difficulty 1 --tags solver_eval
# On the new-game screen: click Balanced Roll, then Start

# Typical combat turn (fully automated)
python3 game_loop.py auto_turn --time-limit 10
# → returns an MCP click plan for End Turn
python3 game_loop.py click_end_turn
# → loop until mission_end

# Chronophobia / pod-destruction combat turns
python3 game_loop.py auto_turn --time-limit 10 --destroy-time-pods

# Inspect the failure corpus
python3 game_loop.py analyze --min-samples 30

# Tune weights and validate
python3 game_loop.py tune --iterations 100 --min-boards 50
```

Manual-play fallback (when the bridge is unavailable):

```bash
python3 game_loop.py read
python3 game_loop.py solve --time-limit 10
python3 game_loop.py click_action 0   # → dispatch via computer_batch, then:
python3 game_loop.py verify_action 0
# ... repeat per action, then click_end_turn
```

---

## CLI reference (`game_loop.py`)

All subcommands are stateless; session state lives in `sessions/active_session.json`.

**State** — `read`, `status`, `verify_action <i>`, `verify [i]`
**Solving & recording** — `solve`, `replay <run_id> <turn>`
**Combat execution** — `auto_turn`, `auto_mission`, `click_action <i>`, `click_end_turn`, `click_balanced_roll`, `execute <i>`, `end_turn`
**Research gate** — `research_next`, `research_submit <id> <json>`, `research_attach_community <id> <notes_json>`, `research_probe_mech <tile> [slot]`
**Analysis & tuning** — `analyze`, `validate <old> <new>`, `tune`, `review_overrides`, `mine_overrides`
**Run management** — `recommend_squad [squad]`, `new_run [squad|auto]`, `snapshot <label>`, `log <msg>`, `mission_end {win|loss}`, `annotate <run_id> <turn> <notes>`
**Utilities** — `calibrate`, `achievements [--sync]`

Standalone scripts:

- `python3 tile_hover.py <A1-H8>` — prints MCP pixel coords for a tile
- `python3 island_select.py [--all]` — random or full-list island picker
- `python3 scrape_wiki.py` — refresh `data/wiki_raw/`

---

## Repository layout

```
game_loop.py                 Primary CLI (dispatches to src/loop/commands.py)
tile_hover.py                Tile → MCP coord utility
island_select.py             Island picker for island-select screen
scrape_wiki.py               Wiki scraper (Playwright + Cloudflare bypass)
CLAUDE.md                    Agent operational rules, protocols, phase playbook
AGENTS.md                    Codex-compatible operational rules adapted from CLAUDE.md
TODO.md                      Achievement checklist (70 total, tier-grouped)
README.md                    This file

src/
  loop/        Session, logger, commands (the stateless CLI backing game_loop.py)
  bridge/      Lua ↔ Python IPC (protocol, reader, writer, modloader.lua)
  model/       Board, Unit, WeaponDef, PawnStats (60+ mechs, 50+ Vek, 100+ weapons)
  solver/      Python wrapper, evaluator, verifier, tuner, analysis, research gate
  control/     MCP click planners (grid_to_mcp, End Turn, weapon icons)
  capture/     Save-file fallback parser + window/grid detection
  strategy/    (placeholder — strategist logic currently lives in loop/commands.py)

rust_solver/   PyO3 extension `itb_solver` (~8k LOC across simulate, enemy, weapons, solver, evaluate, board, movement)
  src/         Rust solver source
  tests/       regression.rs — runs solver against all recorded boards

data/
  ref_*.md                   Hand-authored game mechanics, squads, Vek, pilots, achievements
  known_types.json           Catalog of recognized pawn types / terrain / weapons / screens
  weapon_overrides_staged.jsonl  Weapon-def patch candidates awaiting review
  weapon_penalty_log.json    Desync signature frequency map
  achievements_detailed.json Steam achievement catalog (70 entries)
  squads.json, vek.json, pilots.json, islands.json, mechanics.json
  wiki_raw/                  Scraped wiki pages (source material)

weights/       active.json + v{NNN}_{date}.json history
recordings/    Per-run, per-turn board/solve/verify JSON + failure_db.jsonl
logs/          Per-run decision log (markdown)
sessions/      active_session.json (current run state)
snapshots/     Labeled regression fixtures
tests/         pytest suite (64 files); use `-m regression` for the slow corpus
scripts/       install_modloader.sh, install-hooks.sh, regression.sh, migrate_failure_db.py, regenerate_known_types.py, replay_fuzzy_detector.py, probe_deploy_zone.py
docs/          retrospectives, self_healing_loop_design.md, reference.md, lua_bridge_architecture.md, env_hazards_by_island.md, self_improvement_plan.md
assets/        Game UI screenshots used for calibration
prompts/       Vision prompt templates for the research loop
```

---

## Coordinate conventions

- **Bridge `(x, y)` → visual:** `Row = 8 - x`, `Col = chr(72 - y)`. Example: bridge `(3, 5)` = `C5`. **All communication uses A1–H8 visual notation.**
- **MCP pixel coords:** `grid_to_mcp(x, y)` in `src/control/executor.py` auto-detects the game window via Quartz on macOS or Win32 APIs on Windows, then uses the shared grid calibration. Never hardcode pixel coords - the window moves.
- **UI anchors** (scaled to window size from a 1280×748 reference): End Turn `(95, 78)`, Repair `(105, 553)`, weapon slots `(181, 553)` / `(245, 553)`, Balanced Roll `(791, 530)`.

---

## Testing

```bash
# Python — fast unit tests
pytest -m "not regression"

# Python — slow replay corpus (re-solves ~100 historical failures)
pytest -m regression

# Rust regression (no solver crashes, no empty solutions on active boards)
cd rust_solver && cargo test --test regression --no-default-features

# Everything at once
bash scripts/regression.sh
```

Acceptable failures are tracked in `tests/known_issues.json` (scoped by `"python"`, `"rust"`, or `"both"`).

---

## Key design choices

- **Trust the solver.** Manual overrides suppress the failure-db signal the tuner needs. The only exception is an empty solve result (timeout).
- **Conveyors are tile-driven.** If the bridge exposes `conveyor` on any live tile, enemy-phase belts apply before Vek attacks even outside `Mission_Belt`.
- **Mouse clicks only for UI.** No keyboard shortcuts, no portrait clicks, no Tab — just tile centers and the End Turn button.
- **Click tile centers, not sprites.** Sprites render 100–170 px above tile center; `grid_to_mcp` already handles this.
- **Save file only updates at turn boundaries.** The bridge has no such limit; `verify_action` always re-reads fresh bridge state.
- **Every process error becomes a permanent fix.** Mistakes update `AGENTS.md` / `CLAUDE.md` with a guard so they don't recur.

See `AGENTS.md` for the current Codex operational rule set and `CLAUDE.md` for the original source instructions.
