# Into the Breach Achievement Bot

## Project Goal

Build an autonomous bot that earns all 70 achievements in Into the Breach. The game runs natively on macOS. The bot extracts game state via a Lua bridge (file-based IPC) and executes combat actions through bridge commands. Claude Code's computer use (screenshots + mouse/keyboard) handles UI navigation (menus, shop, deployment, rewards).

## Important Context

- Into the Breach is a turn-based tactics game on an 8x8 grid. It is fully deterministic with perfect information — every enemy telegraphs their attacks before you move.
- The ITB-ModLoader (Lua-based) works on Mac via the game's built-in `modloader.lua`. We use a **Lua bridge** (`src/bridge/`) for direct game state extraction and command execution via file-based IPC through `/tmp/`. Mouse/keyboard control via MCP is used for UI navigation (menus, deployment, shop) that the bridge cannot handle.
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

Claude operates as the outer control loop. Each Python CLI command (`game_loop.py read`, `solve`, `execute`, `verify`) is a stateless tool that reads state, computes, outputs, and exits. Claude calls these tools in sequence, interprets their output, and decides what to do next. In combat, mech actions are executed via the Lua bridge (command files). MCP mouse/keyboard is used for UI navigation (menus, deployment, shop, rewards). The session file (`sessions/active_session.json`) persists state between CLI calls.

Grid coordinate mapping (used for MCP clicks during UI navigation and as bridge fallback): mcp_x = OX + 42*(save_x - save_y), mcp_y = OY + 25*(save_x + save_y), where OX/OY are derived from the game window position (auto-detected via Quartz CGWindowListCopyWindowInfo). Step sizes scale with window dimensions. Bridge commands use grid coordinates directly.

**Bridge-to-visual coordinate mapping:** The game displays Row numbers (1-8, left edge) and Column letters (A-H, right edge). Bridge (x,y) maps to visual as: **Row = 8 - x**, **Col = chr(72 - y)** (H for y=0, G for y=1, ..., A for y=7). Example: bridge (3,5) = visual C5 (TankMech). Always use visual A1-H8 notation when communicating tile positions.

**Attack order:** Enemy attacks resolve sequentially in ascending UID order. The bridge provides `attack_order` as a sorted list of enemy UIDs with queued attacks. Earlier attacks mutate the board before later attacks resolve (important for chain effects).

## Core Game Rules (Solver-Critical)

These rules directly affect solver correctness. Always apply them.

**Terrain kills:** Water and Chasm kill non-flying ground units. Lava kills like water but also sets flying units on Fire. Pushing enemies into these is a primary kill method.

**Push mechanics:** Pushing moves a unit 1 tile in a direction. If blocked (by another unit, mountain, or edge), the pushed unit takes 1 bump damage instead of moving. Chain pushing: if A is pushed into B, B does NOT move — A takes bump damage. Push damage is NOT affected by Armor or ACID.

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
3. When using MCP clicks (UI navigation, bridge fallback): click TILE CENTERS, not sprites. Sprites render 100-170px above tile center in MCP coords.
4. After every failed run, analyze the critical turn. Save snapshot first.
5. When using MCP (fallback): select mechs by clicking their PORTRAIT, then clicking board to dismiss popup, then re-clicking portrait. Do NOT rely on Tab for non-consecutive execution. Bridge commands target mechs by UID — no portrait clicks needed.
6. Priority order — buildings > threats > kills > spawns.
7. Bridge state is the source of truth during combat. Re-read after every action. Fall back to save file if bridge is unavailable.
8. Never move onto ACID tiles voluntarily (doubles damage, disables armor).
9. SELF-IMPROVEMENT — Every process error leads to an immediate CLAUDE.md update with a guard/fix to prevent recurrence. Every mistake makes the process permanently better.
10. For MCP clicks (UI navigation, bridge fallback): always use grid_to_mcp() for coordinates. MCP screenshot coords = Quartz logical coords (verified). grid_to_mcp() auto-detects window position via Quartz — no hardcoded offsets. Bridge commands use grid coordinates directly.
11. When using MCP (fallback): arm weapons via keyboard: '1' for primary, '2' for secondary. Bridge commands specify the weapon directly.
12. NEVER press Space (triggers End Turn dialog unexpectedly).
13. Use ALL mech actions every turn. Even suboptimal moves beat skipping.
14. Solver blind spots (temporary, until implemented): No repair action. No environment hazard awareness (air strikes, tidal waves, lightning). The bridge provides environment_danger tiles — use these to inform manual overrides until solver integration is complete.
15. On recovery from crash/timeout, ALWAYS start with cmd_read + cmd_solve. Never resume a previous solution — the board may have changed.
16. Save file (saveData.lua) only updates at TURN BOUNDARIES, not per-mech-action. The Lua bridge does NOT have this limitation — it provides fresh state after each action. When bridge is active, use bridge state for per-mech verification. When using save file fallback, use visual confirmation or wait until after End Turn to verify.
17. When using MCP (fallback): portrait clicks require clicking the portrait, then clicking the board to dismiss pilot popup, then re-clicking portrait. Use coordinates (win.x+65, win.y+Y) where Y is 250/310/365 for portraits 0/1/2. Always wait 2s after open_application before first click. Bridge commands address mechs by UID.
18. During deployment phase, the bridge may provide deployment zone data. If unavailable, deploy by scanning for yellow arrow indicators on valid tiles via MCP screenshots. The deployment zone is computed by the game engine at runtime.
19. HOVER-VERIFY-CLICK — Before every MCP click: (1) mouse_move to the target, (2) screenshot to visually confirm cursor is on the intended element, (3) only then left_click. Prevents misclicks on wrong UI elements.

## Phase Protocols

### COMBAT_PLAYER_TURN

The main loop. Execute every turn in this exact sequence:

1. `game_loop.py read` — Confirm phase is COMBAT_PLAYER_TURN. Review board state, threats, active mechs.
2. `game_loop.py solve` — Get solution (N actions for N active mechs). If empty solution (timeout): take screenshot, play manually.
3. For each action i in 0..N-1:
   a. `game_loop.py execute i` — Execute action via bridge (returns ACK). If bridge unavailable, outputs click plan for MCP.
   b. Bridge: action already executed, wait for animation. MCP fallback: execute clicks via computer-use MCP, wait 2-3 seconds.
   c. `game_loop.py verify` — Confirm mech acted (retries up to 5x at 1.5s intervals).
      - PASS: continue to next mech.
      - FAIL: retry execute once. If still fails, screenshot + diagnose.
   NOTE: Bridge provides per-action state updates — verify via bridge after each mech. Save file fallback only updates after End Turn; in that case trust visual confirmation (dimmed portrait = mech acted) between individual mech actions.
4. `game_loop.py end_turn` — End turn via bridge command (or click End Turn button if bridge unavailable). Wait for animations (minimum 6s).
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
- `execute <index>` — Execute action N via bridge command (returns ACK). Falls back to outputting a click plan for MCP execution if bridge unavailable.
- `end_turn` — Send END_TURN via bridge (or output click plan for End Turn button if bridge unavailable).

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
│   ├── bridge/            # Lua bridge — primary state extraction + command execution
│   │   ├── protocol.py    # IPC protocol (read/write /tmp/ files, atomic ops)
│   │   ├── reader.py      # Read bridge state → Board construction
│   │   └── writer.py      # Write commands for Lua to execute
│   ├── capture/           # Screenshot and window detection
│   │   └── save_parser.py # Lua save file parser (fallback when bridge unavailable)
│   ├── vision/            # Tile extraction, sprite matching, state parsing
│   ├── model/             # Game state dataclasses (Board, Unit, WeaponDef)
│   ├── solver/            # Threat analysis, search, evaluation
│   │   └── evaluate.py    # EvalWeights for configurable scoring
│   ├── control/           # Mouse/keyboard execution
│   │   └── executor.py    # Per-mech click planning, portrait selection
│   ├── strategy/          # Achievement planner, run-level decisions
│   └── main.py            # Legacy entry point (backward compat)
├── sessions/              # Session JSON files (active_session.json)
├── logs/                  # Decision logs (one markdown file per run)
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
