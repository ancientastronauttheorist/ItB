# Into the Breach Achievement Bot

## Project Goal

Build an autonomous bot that earns all 70 achievements in Into the Breach. The game runs natively on macOS. The bot extracts game state via a Lua bridge (file-based IPC). All game actions (combat, UI navigation, menus, shop, deployment, rewards) are performed exclusively via MCP mouse clicks — the user watches in real-time and needs to see every action happen visually.

## Important Context

- Into the Breach is a turn-based tactics game on an 8x8 grid. It is fully deterministic with perfect information — every enemy telegraphs their attacks before you move.
- The ITB-ModLoader (Lua-based) works on Mac via the game's built-in `modloader.lua`. We use a **Lua bridge** (`src/bridge/`) for **state extraction and action execution** via file-based IPC through `/tmp/`. Two execution modes: manual play (MCP mouse clicks for visual play) and speed mode (`auto_turn`/`auto_mission` via bridge commands, 30-100x faster for data collection).
- The game is turn-based with no time pressure (except one specific achievement). The bot can take as long as it needs per turn.
- Into the Breach is available on Steam. App ID: 590380.

## Architecture Overview

The system has 5 layers:

### Layer 0: Game Loop

`game_loop.py` CLI + `src/loop/` (session.py, logger.py, commands.py). Claude is the control loop; Python tools are stateless. Session management, phase detection, command dispatch, decision logging.

### Layer 1: State Extraction

Primary: **Lua bridge** (`src/bridge/`) uses file-based IPC through `/tmp/` to get full game state directly from the game's Lua runtime. The game's `modloader.lua` writes JSON state dumps (`/tmp/itb_state.json`) on turn start/action complete; Python reads state and writes commands (`/tmp/itb_cmd.txt`). Provides richer data than save parsing: targeted tiles, spawning tiles, environment dangers, per-unit active status, **per-enemy attack data** (piQueuedShot target direction from save file, weapon damage/push/TargetBehind from game globals, attack order by ascending UID). Fallback: save file parser (`src/capture/save_parser.py`) when bridge is unavailable. CV pipeline (`src/vision/`) for screens neither can handle (shop, reward selection, menus). Architecture details: `docs/lua_bridge_architecture.md`.

### Layer 2: Game State Model

`src/model/` — Board, Unit, WeaponDef dataclasses. The Board is built from bridge state data (or save data as fallback) and is the single source of truth the solver operates on.

### Layer 3: Solver

`src/solver/` — Constraint-based threat response followed by bounded search. Given a board with known enemy intents, finds the optimal sequence of mech actions. Evaluation function uses configurable `EvalWeights` so achievement targeting can bias scoring without changing the search logic. Enemy attack simulation processes enemies in UID order (matching game's attack resolution), re-traces projectile paths after mech moves, handles TargetBehind (Alpha Hornet behind-hit), and applies full weapon damage to buildings.

### Layer 4: Achievement Strategist

`src/strategy/` — Selects which `EvalWeights` to inject into the solver based on the current achievement target. Manages run-level configuration: squad selection, island order, shop priorities, pilot choices.

### Execution Model: Claude as Controller

Claude operates as the outer control loop. Two execution modes:

- **Manual play (MCP clicks):** Claude calls `read`/`solve`, interprets output, and performs all game actions via MCP mouse clicks. The user watches every action happen visually. Used for menus, shop, rewards, and when the user wants to observe play.
- **Speed mode (bridge commands):** `game_loop.py auto_turn` chains read→solve→execute→end_turn via bridge commands (30-100x faster). `auto_mission` loops auto_turn from deployment through mission end. Used for data collection and rapid play. Falls back to Claude for UI screens (rewards, shop, island map).

The session file (`sessions/active_session.json`) persists state between CLI calls.

Grid coordinate mapping for MCP clicks: use `grid_to_mcp(bridge_x, bridge_y)` in `src/control/executor.py` or `python3 tile_hover.py <TILE>` (e.g. `tile_hover.py C5`). Both auto-detect the game window position via Quartz. For island selection at run start: `python3 island_select.py`.

**Bridge-to-visual coordinate mapping:** The game displays Row numbers (1-8, left edge) and Column letters (A-H, right edge). Bridge (x,y) maps to visual as: **Row = 8 - x**, **Col = chr(72 - y)** (H for y=0, G for y=1, ..., A for y=7). Example: bridge (3,5) = visual C5 (TankMech). Always use visual A1-H8 notation when communicating tile positions.

**Attack order:** Enemy attacks resolve sequentially in ascending UID order. The bridge provides `attack_order` as a sorted list of enemy UIDs with queued attacks. Earlier attacks mutate the board before later attacks resolve (important for chain effects).

## Core Game Rules (Solver-Critical)

These rules directly affect solver correctness. Always apply them.

**Terrain kills:** Water and Chasm kill non-flying ground units. Lava kills like water but also sets flying units on Fire. Pushing enemies into these is a primary kill method.

**Push mechanics:** Pushing moves a unit 1 tile in a direction. If blocked (by another unit, mountain, or edge), the pushed unit takes 1 bump damage instead of moving. If blocked by a building, BOTH the pushed unit AND the building take 1 bump damage (building can be destroyed, losing grid power). Chain pushing: if A is pushed into B, B does NOT move — both take bump damage. Push damage is NOT affected by Armor or ACID.

**Damage types:**
- Weapon damage: reduced by Armor (-1), doubled by ACID
- Push/bump damage (1): ignores Armor and ACID
- Fire damage (1/turn): ignores Armor and ACID
- Blocking damage (1): when a Vek tries to emerge on an occupied tile — ignores Armor and ACID

**Key status effects:**
- Fire: 1 damage/turn start. Removed by repair, water, or freezing
- Frozen: invincible + immobilized. Any damage frees the unit (dealing 0 damage)
- ACID: doubles weapon damage. Persists until unit dies
- Smoke: prevents attack AND repair. Cancels Vek attacks if on smoke tile at execution
- Shield: blocks one instance of damage + all negative effects. Removed by direct damage
- Armor: -1 weapon damage (minimum 0). Does NOT reduce push/fire/blocking damage
- Webbed: cannot move, CAN still attack. Breaks if pushed away from webber

**Mountains:** 2 HP obstacles. Block movement. Can be damaged/destroyed. Become rubble (ground) when destroyed.

**Buildings:** 1 HP. Damage reduces Grid Power. Grid Defense % gives chance to resist (solver assumes 0%).

**Repair action:** Any mech can repair instead of attacking. Heals 1 HP, removes Fire and ACID. Cannot repair if smoked.

Extended rules: see `data/ref_game_mechanics.md`.

## Operational Rules

1. Always verify state after each mech action via `verify_action <i>`. Bridge provides per-action updates; save file only updates at turn boundaries.
2. Never execute mech N+1 before `verify_action N` returns PASS (or you've consciously decided to log+continue past a desync).
3. When clicking tiles: click TILE CENTERS, not sprites. Sprites render 100-170px above tile center in MCP coords. Use `grid_to_mcp()` or `tile_hover.py`; `click_action` does this for you internally.
4. After every failed run, analyze the critical turn. Save snapshot first.
5. Select mechs by clicking their tile on the board. No portraits, no Tab, no keyboard. `click_action` handles this internally for combat actions.
6. Priority order — buildings > threats > kills > spawns.
7. **Manual play: MCP mouse clicks for all visible actions.** When Claude is the control loop, every move/attack/end-turn must be a visible mouse click so the user can watch and verify. The canonical commands for manual combat play are `click_action <i>` (emits a `computer_batch`-ready plan for one mech action) and `click_end_turn`. After dispatching the batch, run `verify_action <i>` to confirm the predicted state landed. **Speed mode:** `auto_turn` / `auto_mission` execute actions via bridge commands internally (30-100x faster). Bridge commands (`execute`, `end_turn`) are NEVER called directly outside of `auto_turn` / `auto_mission`.
8. Never move onto ACID tiles voluntarily (doubles damage, disables armor).
9. SELF-IMPROVEMENT — Every process error leads to an immediate CLAUDE.md update with a guard/fix to prevent recurrence. Every mistake makes the process permanently better.
10. For MCP clicks during deployment / UI elements: use `grid_to_mcp()` or `tile_hover.py` for coordinates. MCP screenshot coords = Quartz logical coords (verified). `grid_to_mcp()` auto-detects window position via Quartz — no hardcoded offsets. For combat tile clicks during a turn, prefer `click_action` which calls `grid_to_mcp()` internally and is calibrated <2px against all 4 corners.
11. **Manual play: MOUSE CLICKS ONLY — no keyboard.** The user watches the game and needs to see every action happen via visible cursor movement and clicks. Never use keyboard shortcuts (Tab, 1/2 for weapons, Q, Space, etc.). The full mouse-only flow for each mech in manual play:
    - `python3 game_loop.py click_action <i>` — emits a `computer_batch` plan: select-tile click → optional move click → weapon-icon click → target-tile click. Dash weapons skip the move click; Repair clicks the Repair button instead of a target; passives are no-ops.
    - Dispatch the batch via `mcp__computer-use__computer_batch`.
    - Wait for the action animation (~3s).
    - `python3 game_loop.py verify_action <i>` — diffs predicted vs actual board state. PASS = continue. DESYNC = log it (the failure_db record IS the useful signal) and continue unless it's `click_miss`.
    - Repeat for each mech.
    - `python3 game_loop.py click_end_turn` — emits a single click on the End Turn button.
    - Dispatch, wait ~6s for the enemy phase, then `read`.
12. NEVER press any keyboard keys during combat. No Space, no Tab, no number keys, no letter keys.
13. Use ALL mech actions every turn. Even suboptimal moves beat skipping.
14. Solver handles environment hazards via `environment_danger_v2`: the bridge provides per-tile damage + kill metadata, the solver simulates the env_danger tick BEFORE Vek attacks (matching the game's interleaved attack order), and air-strike-class deadly threats bypass shield/frozen/armor/ACID. Mech placement on lethal tiles is penalized at -80000.
15. On recovery from crash/timeout, ALWAYS start with cmd_read + cmd_solve. Never resume a previous solution — the board may have changed.
16. Save file (saveData.lua) only updates at TURN BOUNDARIES, not per-mech-action. The Lua bridge does NOT have this limitation. With the bridge active, `verify_action <i>` is the per-mech verification surface — it reads fresh state via `refresh_bridge_state` and diffs against the predicted snapshot the solver captured during `replay_solution`.
17. _(merged into rule 5)_
18. **DEPLOYMENT**: The bridge provides `deployment_zone` data (list of valid [x,y] tiles). `game_loop.py read` prints all deploy tiles with visual notation AND exact MCP pixel coordinates. Use those MCP coords directly with `left_click` to place each mech. Deploy order: the game prompts for each mech sequentially. Click a deploy tile center → mech appears → next mech prompt. Use `tile_hover.py <TILE>` (e.g. `tile_hover.py C7`) for quick single-tile coordinate lookup.
19. **HOVER-VERIFY-CLICK — required for UI elements only.** Before `left_click`-ing any UI element (End Turn button, weapon icons, Repair button, reward/shop screens, the first click after window movement):
    1. `mouse_move` to the target coordinates
    2. `screenshot` to visually confirm the cursor is on the correct element (read the tooltip, check the tile highlight)
    3. Only then `left_click`
    NOT required for combat tile clicks computed by `grid_to_mcp()` (calibrated <2px) — `click_action` handles these directly. **Board clicks are game actions.** Clicking a mech tile selects it. Clicking a highlighted tile executes a move/attack. Don't click random board tiles to dismiss UI.
20. **ALWAYS FOLLOW THE SOLVER — never override. Failures are data, not disasters.** The solver encodes the full game mechanics (push directions, bump damage, projectile re-aiming, terrain interactions, env_danger ordering). Claude's manual analysis of push chains and attack redirection is error-prone and wastes time. Execute exactly what `game_loop.py solve` outputs — same targets, same order. If the solver's plan looks wrong, it's almost certainly Claude's analysis that's wrong, not the solver. When `verify_action` reports a desync, the failure_db record is the useful signal — it feeds the auto-tuner. Overriding the solver suppresses the data the system needs to improve. The only exception: if the solver returns an empty solution (timeout), play manually with screenshot-based reasoning. See `feedback_trust_solver.md` for the rationale.

## Phase Protocols

### DEPLOYMENT

Runs at the start of each mission (turn 0). Place all 3 mechs on valid tiles.

1. `game_loop.py read` — Bridge state includes `deployment_zone` with all valid tiles. Output shows each tile's visual name (e.g. C7), bridge coords, AND MCP pixel coordinates.
2. Choose 3 tiles from the deployment zone. Prioritize positions that:
   - Protect buildings (adjacent to threatened buildings)
   - Block spawn tiles
   - Set up first-turn attacks on visible enemies
3. For each mech (game prompts sequentially):
   a. Click the chosen tile's MCP coordinates (from `read` output).
   b. Wait 1s for the mech to appear.
4. After all 3 mechs deployed, the game transitions to COMBAT_PLAYER_TURN.

**Tools:** `game_loop.py read` prints deploy tiles + MCP coords. `tile_hover.py <TILE>` for quick single-tile lookup (e.g. `python3 tile_hover.py C7`).

### COMBAT_PLAYER_TURN

The main loop. Execute every turn in this exact sequence:

1. `game_loop.py read` — Confirm phase is COMBAT_PLAYER_TURN. Review board state, threats, active mechs.
2. `game_loop.py solve` — Get solution (N actions for N active mechs). The solve recording now includes a per-action `predicted_states` snapshot used by `verify_action`. If empty solution (timeout): take screenshot, play manually.
3. For each action i in 0..N-1:
   a. `python3 game_loop.py click_action <i>` — Read the JSON output (a `computer_batch`-ready plan). Dispatch via `mcp__computer-use__computer_batch`.
   b. Wait ~3s for animation.
   c. `python3 game_loop.py verify_action <i>` — diff predicted vs actual state. Read the result:
      - **PASS**: continue to next mech.
      - **DESYNC [click_miss]**: retry `click_action <i>` ONCE. If still failing, screenshot + log + skip the mech.
      - **DESYNC [other category]**: log to decision log, do NOT retry, do NOT override. The desync record in failure_db is the useful signal. Continue executing the rest of the turn.
4. `python3 game_loop.py click_end_turn` — Dispatch the batch via `computer_batch`.
5. Wait ~6s for the enemy phase. `game_loop.py read` — Check new phase:
   - COMBAT_PLAYER_TURN: next turn, go to step 2. `read` automatically records the previous turn's post-enemy state.
   - MISSION_ENDING / BETWEEN_MISSIONS: mission over, go to MISSION_END.
   - COMBAT_ENEMY_TURN: still animating, wait and re-read.

### MISSION_END

1. Take screenshot to identify reward screen.
2. Navigate reward selection via clicks.
3. `game_loop.py snapshot "mission_N"` — Save state for analysis.
4. Check if island complete. Proceed to ISLAND_MAP or ISLAND_COMPLETE.

### ISLAND_MAP

1. `game_loop.py read` — Review island state.
2. Choose next mission (prioritize bonus objectives for achievement targets).
3. Navigate to mission via clicks.
4. Transition to COMBAT_PLAYER_TURN.

### SHOP

1. Take screenshot — neither save file nor bridge distinguishes shop from map. Use MCP screenshots for shop navigation.
2. Buy grid power repairs first, then weapons/cores per strategy.
3. Navigate via clicks.
4. Transition to ISLAND_MAP for next island.

### ISLAND_SELECT

Appears at the start of each run (world map with 4 corporate islands). **Always pick a random island** for equal coverage across runs.

1. Take screenshot to identify the island selection screen.
2. **Randomly choose** from the 4 corporate islands using `python3 island_select.py`. Output includes the island name, map position, terrain type, and environmental hazards.
3. Click the chosen island on the map. Island positions (MCP pixel coordinates, verified):
   - Archive Inc: green/forested island, upper-left ~(430, 320)
   - R.S.T. Corporation: brown/desert island, center-left ~(560, 540)
   - Pinnacle Robotics: white/icy island, center-right ~(850, 400)
   - Detritus Disposal: dark/rocky island, lower-right ~(1060, 580)
   If positions shift, hover islands to read their name tooltip before clicking.
4. Click through the CEO intro cutscene (click CONTINUE).
5. Transition to ISLAND_MAP.

**Why random:** Equal coverage of all islands ensures the bot encounters diverse environments (tidal waves, air strikes, lightning, conveyor belts) and Vek types, improving solver robustness and achievement coverage.

### RUN_END

1. `game_loop.py snapshot "run_end"` — Save final state.
2. If defeat: analyze critical turns from decision log (Rule 4).
3. Check achievement progress.
4. Start new run with next achievement target.

### ERROR_RECOVERY

- **Unexpected screen:** Take screenshot, log to decision log, diagnose visually.
- **State not updating:** Check bridge first (refresh_bridge_state). If bridge unavailable, retry save file verify up to 5x with 1.5s delay (7.5s max).
- **Grid power = 0:** Log game over, snapshot, analyze.
- **Crash/timeout:** Start fresh with `cmd_read` + `cmd_solve` (Rule 15). Never resume old solution.

## Game Loop Command Reference

All commands are subcommands of `game_loop.py`. Each is stateless: read state, compute, output, exit.

**State Reading:**
- `read` — Read game state via bridge (primary) or save file (fallback). Detect phase, dump board state + threats + active mechs.
- `verify [index]` — Re-parse save file, confirm mech acted (legacy save-parser-based path; retries up to 5× at 1.5s). Superseded by `verify_action` in bridge mode.
- `verify_action <index>` — Per-action diff: refreshes the bridge, diffs the actual state against the snapshot the solver captured for action `<index>` during `replay_solution`, classifies the diff (click_miss / death / damage_amount / push_dir / grid_power / status / terrain / tile_status / spawn / pod), and writes a desync record to `failure_db.jsonl`. Never re-solves, never overrides.
- `status` — Quick summary: turn, grid power, mech HP, threats, objectives.

**Combat (manual play, MCP mouse clicks):**
- `solve` — Run solver, store solution in session, output action sequence. Solve recording includes per-action `predicted_states`.
- `click_action <index>` — Pure planner. Emits a `computer_batch`-ready batch of `left_click` ops for ONE mech action (select-tile → optional move → weapon icon → target). Branches on weapon type: dash weapons skip the move click, Repair clicks the Repair button instead of a target, passives are no-ops.
- `click_end_turn` — Pure planner. Emits a single click on the End Turn button.
- `execute <index>` / `end_turn` — Bridge-mode action commands. Used internally by `auto_turn`. In manual play, use `click_action` / `click_end_turn` instead.

**State Recording:**
- `read` and `solve` both auto-record full game state to `recordings/<run_id>/m<NN>_turn_<NN>_<label>.json`. Each recording includes the complete bridge JSON (64 tiles, all units, targets, spawns) plus the solver output.
- `read` auto-detects post-enemy turns (turn number advanced past solved turn) and records `*_post_enemy.json` (predicted vs actual comparison) and `*_triggers.json` (detected solver failures). The dedup guard prevents duplicate records when both `read` and `auto_mission`'s exit-flush try to record the same `(mission, turn)` pair.
- `solve` recordings are enriched: structured actions (uid/move/weapon/target), per-action `ActionResult`, **per-action `predicted_states`** (input to `verify_action`), predicted post-enemy board state, score component breakdown, and search statistics.

**Analysis:**
- `replay <run_id> <turn> [--time-limit 30]` — Reconstruct a Board from a recorded board JSON and re-run the solver. Compares new solution with original.
- `analyze [--min-samples N]` — Read failure_db.jsonl and report patterns by trigger / severity / squad / island. Gates squad/island/temporal breakdowns behind sample-count minimums.
- `validate <old.json> <new.json> [--failures-only] [--time-limit N]` — Compare two weight versions across recorded boards. Default mode replays every board and reports new_better/old_better/ties under the fixed-score scorer plus regression gates. `--failures-only` restricts to boards in failure_db (deduped by `(run_id, mission, trigger)`) and applies the stricter Fixed/Regressed/Neutral rule (Fixed = trigger no longer fires AND new_score >= old_score). Audit-tagged runs are filtered out of both modes.
- `tune [--iterations N] [--min-boards N] [--time-limit N]` — Auto-tune solver weights. Hybrid objective: `mean_fixed_score - 100 * fired_failure_count` (λ calibrated against ~1240 typical fixed_score range so one avoided failure ≈ one building).

**Speed Mode:**
- `auto_turn [--time-limit 10]` — Execute one combat turn via bridge: read→solve→execute all→end turn. ~10-25s per turn (30-100x faster than MCP clicks).
- `auto_mission [--max-turns 20]` — Full mission via bridge: auto-deploy→combat loop→mission end. Final turn is force-flushed to failure_db on exit. Falls back to Claude for reward/shop/map screens.

**Run Management:**
- `new_run <squad> [--achieve X Y] [--difficulty N] [--tags audit ...]` — Initialize new session. Use `--tags audit` for environment-audit playthroughs so the failures don't pollute the tuner training corpus.
- `snapshot <label>` — Save current state for regression testing.
- `log <message>` — Append Claude's reasoning to the decision log.

## Achievement Context

9/70 complete, 61 remaining across 4 difficulty tiers (Green >40%, Yellow 20-40%, Orange 10-20%, Red <10%).

- Squad-specific achievements require specific squads — check `data/ref_achievement_strategies.md` for setup.
- Cumulative achievements (reputation, civilians, pilot reuse) accrue across runs.
- Achievement strategies modify solver weights via `EvalWeights` in `src/solver/evaluate.py`.
- Detailed metadata: `data/achievements_detailed.json`.
- Full achievement checklist with tiers: `TODO.md`.

## Knowledge Base

Compiled reference files in `data/` — read the relevant file when you need detailed game data:

| File | Contents | Read when... |
|------|----------|-------------|
| `data/ref_squads_and_mechs.md` | All 13 squads, mechs (class/HP/move), weapons (damage/effect/upgrades), squad achievements, strategies | Working on specific squad, achievement planning, weapon logic |
| `data/ref_vek_bestiary.md` | All Vek (HP/move/attack/damage), alphas, Psions, Leaders, Bosses, Bots | Building solver, vision system, threat analysis |
| `data/ref_pilots.md` | All pilots, abilities, corporations, power costs | Pilot selection, run planning |
| `data/ref_game_mechanics.md` | Full terrain/status/damage/push rules, turn structure, grid defense, reputation, islands | Building/debugging solver, verifying rules |
| `data/ref_achievement_strategies.md` | Per-achievement strategy, bot approach, setup, difficulty rating | Achievement strategist, run configuration |

Curated JSON data in `data/` — structured, verified game data (machine-readable for code):

| File | Contents |
|------|----------|
| `data/squads.json` | All squads with mechs, weapons, upgrades, achievements (1092 lines) |
| `data/vek.json` | All Vek with stats, attacks, alpha variants (630 lines) |
| `data/pilots.json` | Pilot system, XP, all pilots with abilities (252 lines) |
| `data/mechanics.json` | Terrain, status effects, damage rules (387 lines) |
| `data/terrain_status_mechanics.json` | Extended terrain + status interactions (1374 lines) |
| `data/islands.json` | Island structure, environments, missions (474 lines) |
| `data/achievements_detailed.json` | All 70 achievements with detailed metadata (751 lines) |
| `data/grid_reference.json` | Game window/grid pixel coordinates (108 lines) |
| `data/board_state_test.json` | Test board state for solver development (1031 lines) |

Raw wiki data in `data/wiki_raw/*.json` (135 files) for individual unit deep-dives.

## File Structure

```
itb-bot/
├── CLAUDE.md              # This file — operational manual
├── TODO.md                # Development roadmap + achievement checklist
├── game_loop.py           # CLI entry point — dispatches to src/loop/
├── island_select.py       # Random island picker for equal coverage across runs
├── src/
│   ├── loop/              # Game loop modules
│   │   ├── session.py     # RunSession state, file-locked persistence
│   │   ├── logger.py      # Append-only markdown decision log
│   │   └── commands.py    # All CLI subcommand implementations
│   ├── bridge/            # Lua bridge — state extraction + action execution (via auto_turn/auto_mission)
│   │   ├── protocol.py    # IPC protocol (read/write /tmp/ files, atomic ops)
│   │   ├── reader.py      # Read bridge state → Board construction
│   │   └── writer.py      # Write commands for Lua to execute
│   ├── capture/           # Screenshot and window detection
│   │   └── save_parser.py # Lua save file parser (fallback when bridge unavailable)
│   ├── vision/            # Tile extraction, sprite matching, state parsing
│   ├── model/             # Game state dataclasses (Board, Unit, WeaponDef)
│   ├── solver/            # Threat analysis, search, evaluation
│   │   └── evaluate.py    # EvalWeights for configurable scoring
│   ├── control/           # MCP mouse click coordinate calculation
│   │   └── executor.py    # Per-mech click planning (board-click selection,
│   │                      # weapon-type classifier, no portraits, no keyboard)
│   ├── strategy/          # Achievement planner, run-level decisions
│   └── main.py            # Legacy entry point (backward compat)
├── sessions/              # Session JSON files (active_session.json)
├── logs/                  # Decision logs (one markdown file per run)
├── recordings/            # Per-turn state recordings (board + solver) for replay/analysis
├── snapshots/             # Saved states for regression testing
├── assets/
│   ├── sprites/           # Reference sprite atlas
│   └── screenshots/       # Saved screenshots for testing
├── docs/
│   └── lua_bridge_architecture.md  # Bridge design, protocol, IPC details
├── weights/               # EvalWeights JSON files (active.json, versioned snapshots)
├── tests/                 # Unit tests for solver, state extraction
└── data/
    ├── ref_squads_and_mechs.md
    ├── ref_vek_bestiary.md
    ├── ref_pilots.md
    ├── ref_game_mechanics.md
    ├── ref_achievement_strategies.md
    ├── squads.json
    ├── vek.json
    ├── pilots.json
    ├── mechanics.json
    ├── terrain_status_mechanics.json
    ├── islands.json
    ├── achievements_detailed.json
    ├── grid_reference.json
    ├── board_state_test.json
    └── wiki_raw/              # 135 raw wiki JSON files
```

## Current Status

Self-correcting system overhaul Phases 0–6 complete, plus live M3 calibration. Combat play uses `click_action <i>` + `verify_action <i>` + `click_end_turn` for the canonical mouse-only flow with live-measured UI offsets (weapon slot at window-relative (191, 528), Repair at (111, 528), End Turn unchanged at (95, 78)), and `plan_single_mech` now intersperses `wait` ops between clicks so rapid `computer_batch` dispatches don't eat the weapon-arm step. Per-action desyncs land in `failure_db.jsonl` as data for the auto-tuner instead of triggering manual overrides. Solver simulates per-tile env_danger (lethal flag bypasses shield/frozen/armor/ACID) and weights `mech_killed` at -80000. Tuner objective is `mean_fixed_score - 100 * fired_failure_count` with audit-tagged runs filtered out. `validate --failures-only` gates new weight versions on Fixed/Regressed/Neutral counts under stricter rules. Game loop CLI operates in dual mode: manual play (MCP clicks via `click_action` / `verify_action` / `click_end_turn`) and speed mode (`auto_turn` / `auto_mission` via bridge commands, 30–100x faster). M5 infrastructure is verified (`environment_danger_v2` field populates correctly after `modloader.lua` is reinstalled into the Steam game directory), but the live sweep across all 6 environment types remains user homework because env hazards are RNG-assigned and require multiple re-rolls to surface.

**Modloader install footgun:** `src/bridge/modloader.lua` is NOT auto-installed. After editing it, copy it to `~/Library/Application Support/Steam/steamapps/common/Into the Breach/Into the Breach.app/Contents/Resources/scripts/modloader.lua` and restart the game, otherwise the game keeps running the stale pre-change version. Added to the follow-up list.
