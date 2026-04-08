# Into the Breach Achievement Bot

## Project Goal

Build an autonomous bot that earns all 70 achievements in Into the Breach. The game runs natively on macOS. The bot extracts game state via a Lua bridge (file-based IPC). All game actions (combat, UI navigation, menus, shop, deployment, rewards) are performed exclusively via MCP mouse clicks — the user watches in real-time and needs to see every action happen visually.

## Important Context

- Into the Breach is a turn-based tactics game on an 8x8 grid. It is fully deterministic with perfect information — every enemy telegraphs their attacks before you move.
- The ITB-ModLoader (Lua-based) works on Mac via the game's built-in `modloader.lua`. We use a **Lua bridge** (`src/bridge/`) for **state extraction only** via file-based IPC through `/tmp/`. All actions (combat moves, attacks, end turn, UI navigation) are performed via MCP mouse clicks — never bridge commands, never keyboard shortcuts.
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

Claude operates as the outer control loop. Python CLI commands (`game_loop.py read`, `solve`) are stateless tools that read state, compute, and output. Claude calls these tools, interprets output, and performs all game actions via MCP mouse clicks. The bridge is used ONLY for reading state — never for executing actions. The session file (`sessions/active_session.json`) persists state between CLI calls.

Grid coordinate mapping for MCP clicks: use `grid_to_mcp(bridge_x, bridge_y)` in `src/control/executor.py` or `python3 tile_hover.py <TILE>` (e.g. `tile_hover.py C5`). Both auto-detect the game window position via Quartz.

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

1. Always verify state after each mech execution. Bridge provides per-action updates; save file only updates at turn boundaries.
2. Never execute mech N+1 before verifying mech N succeeded.
3. When clicking tiles: click TILE CENTERS, not sprites. Sprites render 100-170px above tile center in MCP coords.
4. After every failed run, analyze the critical turn. Save snapshot first.
5. Select mechs by clicking their tile on the board (use `tile_hover.py` for coords). No need to use sidebar portraits. NEVER use Tab or any keyboard key.
6. Priority order — buildings > threats > kills > spawns.
7. **ALL actions via MCP mouse clicks ONLY.** The bridge is for reading state (`game_loop.py read`/`solve`). NEVER use `game_loop.py execute` or bridge commands (MOVE, ATTACK, SKIP, END_TURN) to perform actions — even if they work, the user cannot see invisible commands. Every move, attack, and end turn must be a visible mouse click so the user can watch and verify. Re-read bridge state after every action to confirm it worked.
8. Never move onto ACID tiles voluntarily (doubles damage, disables armor).
9. SELF-IMPROVEMENT — Every process error leads to an immediate CLAUDE.md update with a guard/fix to prevent recurrence. Every mistake makes the process permanently better.
10. For MCP clicks: always use grid_to_mcp() or `tile_hover.py` for coordinates. MCP screenshot coords = Quartz logical coords (verified). grid_to_mcp() auto-detects window position via Quartz — no hardcoded offsets.
11. **MOUSE CLICKS ONLY — no keyboard, no bridge commands.** The user watches the game and needs to see every action happen via visible cursor movement and clicks. Never use keyboard shortcuts (Tab, 1/2 for weapons, Q, Space, etc.) or bridge execute commands. The full mouse-only sequence for each mech:
    - **Select mech**: Click the mech's tile on the board (use `tile_hover.py <TILE>` for coords)
    - **Move**: Click the destination tile center (green highlighted tile)
    - **Arm weapon**: Click the weapon icon in the bottom panel
    - **Attack**: Click the target tile center (orange highlighted tile)
    - **Disarm weapon**: Right-click anywhere to cancel weapon targeting
    - **End turn**: Click the "End Turn" button in the top-left
    - **Preferred order: MOVE FIRST, then arm weapon and attack.** Moving first ensures the weapon fires from the correct position. If weapon is armed accidentally, right-click to disarm.
    - Use `tile_hover.py` or `grid_to_mcp()` for precise tile coordinates.
12. NEVER press any keyboard keys during combat. No Space, no Tab, no number keys, no letter keys.
13. Use ALL mech actions every turn. Even suboptimal moves beat skipping.
14. Solver handles environment hazards (tidal waves, etc.): the bridge provides `environment_danger` tiles, the solver avoids placing mechs on them and tries to push enemies onto them. `game_loop.py read` prints danger tiles. Remaining blind spots: air strikes, lightning (less common).
15. On recovery from crash/timeout, ALWAYS start with cmd_read + cmd_solve. Never resume a previous solution — the board may have changed.
16. Save file (saveData.lua) only updates at TURN BOUNDARIES, not per-mech-action. The Lua bridge does NOT have this limitation — it provides fresh state after each action. When bridge is active, use bridge state for per-mech verification. When using save file fallback, use visual confirmation or wait until after End Turn to verify.
17. Select mechs by clicking their tile on the board, not the sidebar portraits. Portraits show pilot popups that require extra clicks to dismiss. Board-click selection is simpler and more reliable. Always wait 2s after open_application before first click.
18. **DEPLOYMENT**: The bridge provides `deployment_zone` data (list of valid [x,y] tiles). `game_loop.py read` prints all deploy tiles with visual notation AND exact MCP pixel coordinates. Use those MCP coords directly with `left_click` to place each mech. Deploy order: the game prompts for each mech sequentially. Click a deploy tile center → mech appears → next mech prompt. Use `tile_hover.py <TILE>` (e.g. `tile_hover.py C7`) for quick single-tile coordinate lookup.
19. **HOVER-VERIFY-CLICK — mandatory for EVERY click.** Never call `left_click` without this 3-step sequence:
    1. `mouse_move` to the target coordinates
    2. `screenshot` to visually confirm the cursor is on the correct element (read the tooltip, check the tile highlight)
    3. Only then `left_click`
    **Board clicks are game actions.** Clicking a mech tile selects it. Clicking a highlighted tile executes a move/attack. Don't click random board tiles to dismiss UI — use the End Turn area or weapon panel as neutral click targets if needed.

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
2. `game_loop.py solve` — Get solution (N actions for N active mechs). If empty solution (timeout): take screenshot, play manually.
3. For each action i in 0..N-1:
   a. Execute action via MCP mouse clicks: click mech tile on board → click move tile → click weapon icon → click target tile. Right-click to disarm if needed. Use `tile_hover.py` for coordinates.
   b. Wait 2-3 seconds for animation to complete.
   c. `game_loop.py read` — Re-read bridge state to verify mech acted (check active=False for that mech).
      - PASS: continue to next mech.
      - FAIL: retry the click sequence. If still fails, screenshot + diagnose.
   NOTE: Verify via bridge state after each mech action.
4. Click the "End Turn" button (top-left of game UI). Wait for animations (minimum 6s).
5. `game_loop.py read` — Check new phase:
   - COMBAT_PLAYER_TURN: next turn, go to step 2.
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
2. **Randomly choose** from the 4 corporate islands: Archive Inc, R.S.T. Corporation, Pinnacle Robotics, Detritus Disposal. Use `python3 -c "import random; print(random.choice(['archive','rst','pinnacle','detritus']))"` to pick.
3. Click the chosen island on the map. Island positions (approximate screen regions):
   - Archive Inc: upper-left area
   - R.S.T.: lower-left area
   - Pinnacle: upper-right area
   - Detritus: right area
   If positions are unclear, hover islands to read their name tooltip before clicking.
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
- `verify [index]` — Re-parse save file, confirm mech acted. Retries up to 5x at 1.5s. (Note: currently save-parser-only; bridge verify not yet implemented.)
- `status` — Quick summary: turn, grid power, mech HP, threats, objectives.

**Combat:**
- `solve` — Run solver, store solution in session, output action sequence.
- `execute` / `end_turn` — **DO NOT USE.** These send bridge commands. All actions must be MCP mouse clicks.

**State Recording:**
- `read` and `solve` both auto-record full game state to `recordings/<run_id>/turn_<N>_<label>.json`. Each recording includes the complete bridge JSON (64 tiles, all units, targets, spawns) plus the solver output. Used for replay, regression testing, and solver improvement.
- `read` auto-detects post-enemy turns (turn number advanced past solved turn) and records `turn_N_post_enemy.json` (predicted vs actual comparison) and `turn_N_triggers.json` (detected solver failures).
- `solve` recordings are enriched: structured actions (uid/move/weapon/target), per-action `ActionResult`, predicted post-enemy board state, score component breakdown, and search statistics.

**Analysis:**
- `replay <run_id> <turn> [--time-limit 30]` — Reconstruct a Board from a recorded `turn_N_board.json` and re-run the solver. Compares new solution with original. Use for testing solver fixes against historical failures.

**Run Management:**
- `new_run <squad> [--achieve X Y]` — Initialize new session with squad and achievement targets.
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
├── src/
│   ├── loop/              # Game loop modules
│   │   ├── session.py     # RunSession state, file-locked persistence
│   │   ├── logger.py      # Append-only markdown decision log
│   │   └── commands.py    # All CLI subcommand implementations
│   ├── bridge/            # Lua bridge — state extraction only (read, never execute)
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
│   │   └── executor.py    # Per-mech click planning, portrait selection
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

Phase 4 complete. Game loop CLI implemented. Lua bridge operational with per-enemy attack data (piQueuedShot, weapon damage, TargetBehind, attack order). Solver overhauled: proper building damage model, projectile path re-simulation, sequential enemy resolution by UID, melee TargetBehind support, friendly-fire penalties. `cmd_solve()` now uses bridge data instead of save parser. Claude-as-the-loop architecture operational.
