# Into the Breach Achievement Bot

An autonomous bot that plays [Into the Breach](https://subsetgames.com/itb.html) on macOS, aiming to earn all 70 Steam achievements. Claude is the control loop; Python + Rust handle state extraction, combat planning, and click synthesis; a Lua mod-loader bridge wires everything into the running game.

Status: **17 / 70 achievements earned** (live from Steam Web API via `python3 game_loop.py achievements`; see `TODO.md` for the checklist).

---

## How it works

The game runs natively. State flows out through a Lua mod hook that writes `/tmp/itb_state.json`; commands flow back through `/tmp/itb_cmd.txt`, ACKed via `/tmp/itb_ack.txt`, with a heartbeat file to detect a hung bridge. For UI screens the bridge can't drive (deployment, menus, shop, rewards, island map), the bot emits pixel-coordinate click plans and dispatches them via the `computer-use` MCP.

### Five-layer architecture

| Layer | Code | Role |
|---|---|---|
| 0 — Game loop | `game_loop.py` + `src/loop/` | Stateless CLI. Every invocation: load session → compute → save. Claude is the orchestrator. |
| 1 — State extraction | `src/bridge/` (primary), `src/capture/` (fallback save-file parser) | Bridge gives per-sub-action updates, targeted tiles, env hazards with kill flag, deployment zone. Save file only updates at turn boundaries. |
| 2 — Game state | `src/model/` | `Board`, `Unit`, `WeaponDef` — the solver's single source of truth. |
| 3 — Solver | `rust_solver/` (`itb_solver` PyO3 extension) + `src/solver/simulate.py` (Python parity) | Threat-response bounded permutation search with a ~50-field `EvalWeights`. |
| 4 — Strategist | Distributed across `src/loop/commands.py` (`cmd_new_run`), `weights/active.json`, achievement metadata in `data/` | Picks weights, squad, island, shop choices per achievement target. Still largely manual; no per-achievement weight remapping yet. |

### Self-healing research loop

When `read` encounters an unknown pawn type, terrain, weapon, or UI screen, it returns `RESEARCH_REQUIRED`. The loop then:

1. `research_next` emits an MCP capture plan (crop regions + Vision prompts).
2. Claude dispatches the plan, runs Vision on each crop, submits JSON via `research_submit`.
3. If confidence is low, community notes (Steam / Reddit) are fetched and attached via `research_attach_community`.
4. Results land in `data/known_types.json`, `data/weapon_overrides_staged.jsonl`, and `data/weapon_penalty_log.json`.

See `docs/self_healing_loop_design.md` for the four-phase design (Instrumentation → Passive Response → Research Pipeline → Active Response).

### Failure database and auto-tuning

Every desync between predicted and actual board writes a record to `recordings/failure_db.jsonl`. Three commands consume it:

- `analyze` — pattern breakdowns by trigger, tier, severity, squad, island.
- `tune` — random search + coordinate refinement on `EvalWeights`; objective is `mean_fixed_score − 100 × failure_count`.
- `validate` — replays all recorded boards under two weight versions; gates deployment on ≤20% regression rate and zero critical building-loss regressions.

Tuned weights land in `weights/v{NNN}_{date}.json`; the deployed copy is `weights/active.json`.

---

## Setup

### Prerequisites

- macOS (Quartz used for window detection)
- Python 3.9+
- Rust toolchain
- `maturin` (`pip install maturin`)
- Into the Breach on Steam (App ID `590380`), with [ITB-ModLoader](https://github.com/itb-community/ITB-ModLoader) installed

### Install the Lua bridge

```bash
bash scripts/install_modloader.sh   # copies src/bridge/modloader.lua into the Steam app bundle
# then restart Into the Breach
```

Re-run after any edit to `src/bridge/modloader.lua`.

### Build the Rust solver

```bash
cd rust_solver
maturin build --release
pip3 install --user --force-reinstall target/wheels/itb_solver-0.1.0-cp39-cp39-macosx_11_0_arm64.whl
```

Re-run after any edit to `rust_solver/src/*.rs`.

### Git hooks

```bash
bash scripts/install-hooks.sh
```

### Secrets

`.env` (gitignored) holds `STEAM_API_KEY` and `STEAM_ID` for achievement queries.

---

## Quick start

```bash
# Start a new run
python3 game_loop.py new_run rift_walkers --difficulty 2 --tags exploration

# Typical combat turn (fully automated)
python3 game_loop.py auto_turn --time-limit 10
# → returns an MCP click plan for End Turn
python3 game_loop.py click_end_turn
# → loop until mission_end

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
**Run management** — `new_run <squad>`, `snapshot <label>`, `log <msg>`, `mission_end {win|loss}`, `annotate <run_id> <turn> <notes>`
**Utilities** — `calibrate`, `achievements`

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
TODO.md                      Achievement checklist (70 total, tier-grouped)
README.md                    This file

src/
  loop/        Session, logger, commands (the stateless CLI backing game_loop.py)
  bridge/      Lua ↔ Python IPC (protocol, reader, writer, modloader.lua)
  model/       Board, Unit, WeaponDef, PawnStats (60+ mechs, 50+ Vek, 100+ weapons)
  solver/      Python parity simulator, evaluator, tuner, analysis, research gate
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
tests/         pytest suite (33 files); use `-m regression` for the slow corpus
scripts/       install_modloader.sh, install-hooks.sh, regression.sh, migrate_failure_db.py, regenerate_known_types.py, replay_fuzzy_detector.py, probe_deploy_zone.py
docs/          self_healing_loop_design.md, reference.md, lua_bridge_architecture.md, env_hazards_by_island.md, self_improvement_plan.md
assets/        Game UI screenshots used for calibration
prompts/       Vision prompt templates for the research loop
```

---

## Coordinate conventions

- **Bridge `(x, y)` → visual:** `Row = 8 - x`, `Col = chr(72 - y)`. Example: bridge `(3, 5)` = `C5`. **All communication uses A1–H8 visual notation.**
- **MCP pixel coords:** `grid_to_mcp(x, y)` in `src/control/executor.py` auto-detects the game window via Quartz (calibrated <2px against all four corners on 2026-04-07). Never hardcode pixel coords — the window moves.
- **UI anchors** (scaled to window size from a 1280×748 reference): End Turn `(95, 78)`, Repair `(111, 528)`, weapon slots `(191, 528)` / `(255, 528)`, Balanced Roll `(791, 530)`.

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
- **Mouse clicks only for UI.** No keyboard shortcuts, no portrait clicks, no Tab — just tile centers and the End Turn button.
- **Click tile centers, not sprites.** Sprites render 100–170 px above tile center; `grid_to_mcp` already handles this.
- **Save file only updates at turn boundaries.** The bridge has no such limit; `verify_action` always re-reads fresh bridge state.
- **Every process error becomes a permanent fix.** Mistakes update CLAUDE.md with a guard so they don't recur.

See `CLAUDE.md` for the full operational rule set.
