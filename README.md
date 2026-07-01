# Into the Breach Achievement Bot

An autonomous bot that plays [Into the Breach](https://subsetgames.com/itb.html) on macOS and Windows, aiming to earn all 70 Steam achievements. Codex-style agents are the live control loop; Python + Rust handle state extraction, combat planning, and click synthesis; a Lua mod-loader bridge wires everything into the running game.

Status: **66 / 70 Steam/client-cache confirmed and locally proven**. **Feed the Flame**, **Complete Victory**, **Lightning War**, and **Spider Breeding** reconciled in the Steam/API checklist by 2026-06-29. **Let's Walk** unlocked locally/offline on 2026-06-29 in Mist Eaters run `20260629_073305_098`: the in-game squad achievement panel showed the lit Let's Walk icon after a visible Control Shot moved a Scarab from E2 to H3, and Into the Breach logged `Set Steam Achievement Ach_Squad_Mist_2`. **Hold the Door** Steam-confirmed from Bombermechs run `20260630_084844_192` with an unlock time of 2026-06-30 08:31 CDT; later local profile evidence (`Squad_Bomber_1 = 1`, with installed localization mapping `Ach_Squad_Bomber_1` to Hold the Door) corroborates the unlock but is not the popup time. **Core of the Earth** unlocked locally on restart on 2026-06-30 after Cataclysm run `20260630_143648_199` secured the R.S.T. island pit-kill route. **No Survivors** surfaced on restart on 2026-07-01; durable proof found `Set Steam Achievement Ach_Squad_Bomber_2` in `log.txt` and the Steam client cache marked No Survivors achieved with unlock time 2026-07-01 10:20:44 CDT, while the profile flag still lagged at `Squad_Bomber_2 = 0` during proof. **Working Together** unlocked locally/offline on 2026-07-01 in Arachnophiles run `20260701_103831_478`: Cold Storage `Mission_SnowBattle` turn 2 put Slide at E2 with Bulk F2, Scorpio E3, Arachnoid D2, and Snowlaser E1 around it, then fired Area Shift at E3; the pause-menu squad-achievement panel showed the lit middle icon, Into the Breach logged `Set Steam Achievement Ach_Squad_Spiders_2`, and the Steam client cache marked it achieved with unlock time 2026-07-01 11:31:47 CDT. Steam offline mode or missing sync credentials can delay local checklist reconciliation, so report each source precisely.

Recent highlight: the merged line now carries the Lightning War speed infrastructure from `codex`, the Feed the Flame / Heat Sinkers simulator work, the Bombermechs Complete Victory final-cave proof, the Spider Breeding Arachnophiles proof, the Mist Eaters Let's Walk visible-Control-Shot proof, the Bombermechs Hold the Door spawn-blocking proof, the Cataclysm Core of the Earth pit-kill proof, the Bombermechs No Survivors restart/cache proof, and the Arachnophiles Working Together pause-menu proof. Lightning War was won by treating UI traversal as a timer-safe speedrun graph: pause before reasoning, read timer truth from screenshots, use deterministic deployment/reward/shop scripts, and keep combat boring and reliable through the Rust solver. Let's Walk closed after the solver and execution path learned to prefer calibrated visible `Science_TC_Control` clicks instead of raw bridge effects, with progress verified through the pause-menu achievement tooltip. Hold the Door closed once the Bombermechs route leaned into the current AE target of 15 blocked Emerging Vek by the end of Island 2, using Walking Bombs, body blocks, and Force Swap positioning while keeping the critical-grid Archive run alive. Core of the Earth closed after the Cataclysm route biased combat toward chasm drops, avoided low-payoff trap routing, and fixed Tri-Rocket edge-push simulation before the restart surfaced the achievement popup. No Survivors closed with a delayed restart popup and proof from both the Into the Breach log and Steam's local achievement cache. Working Together closed after the simulator began emitting an Area Shift four-unit event and the achievement overlay learned to score both the final shift and the surrounding setup geometry.

Recent unlocks: **Working Together** is proven from Arachnophiles run `20260701_103831_478`: `achievement_proof "Working Together"` found `Ach_Squad_Spiders_2` in the game log and Steam client cache, and the pause-menu squad panel showed the colorful middle icon immediately after the four-unit Area Shift. **No Survivors** is proven from the 2026-07-01 restart popup path: `achievement_proof "No Survivors"` found `Ach_Squad_Bomber_2` in the game log and Steam client cache. **Core of the Earth** is locally proven from the 2026-06-30 restart popup after Cataclysm run `20260630_143648_199`, and the 2026-07-01 achievement sync marks it complete. **Hold the Door** is Steam-confirmed from the Bombermechs run with an unlock time of 2026-06-30 08:31 CDT. **Let's Walk** is locally proven from visible Control Shot movement crossing the 120-space threshold on Archive island. **Spider Breeding** is confirmed from Arachnoid Injector kill credit reaching 15 spawns on one Corporate Island. **Feed the Flame**, **Complete Victory**, and **Lightning War** are Steam-cache confirmed as of 2026-06-26. **Stay With Me!** unlocked and Steam-cache synced on 2026-06-17 in Mist Eaters Easy R.S.T. play; **Lucky Start** reconciled before that run. Earlier major milestones include **On the Backburner**, **Chronophobia**, **Powered Blast**, **Trick Shot**, **Immortal**, **Loot Boxes!**, **Engineering Dropout**, **Class Specialist**, **Change the Odds**, **Mech Specialist**, **Flight Specialist**, **Distant Friends**, **Hold the Line**, **Healing**, **Overkill**, **Untouchable**, **Unstable Ground**, **This is Fine**, **Quantum Entanglement**, **Adaptable Victory**, **There is No Try**, **Perfect Strategy**, **Ramming Speed**, **Chain Attack**, **Squads Victory**, **Stormy Weather**, and **Hard Victory**. See `TODO.md` for the checklist.

Current milestone: the working tracker is 66/70 proven. Remaining cleanup can pivot to Arachnophiles **Efficient Explosives**, Heat Sinkers **Boosted** / **Maximum Firepower**, or Cataclysm **Miner Inconvenience**.

### Lightning War retrospective

**Lightning War** took roughly three weeks because it attacked the weakest part of the original architecture: the bot was strong at solving turns, but the achievement measured every second spent outside pause. The winning direction was to treat UI navigation as part of the speedrun, not as a wrapper around combat. The loop evolved toward a strict primitive: capture a visible screenshot, immediately pause with `Esc`, verify the pause menu visually, and only then let the LLM reason.

The turning point was a human calibration Q&A before the long successful run. The user's answers redirected the work toward a timer-first machine: the solver was already strong enough, mission shopping was usually wasted timer, the highlighted 8x8 preview board was the fastest route target, deployment should use the fast helper, shop policy should be deterministic, Advanced Edition could stay off, and screenshot/timing collection was worth it if bounded. The detailed sprint plan lives in [docs/agent/lightning-war-proof-gated-sprint.html](docs/agent/lightning-war-proof-gated-sprint.html).

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
