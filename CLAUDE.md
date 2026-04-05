# Into the Breach Achievement Bot

## Project Goal

Build an autonomous bot that earns all 70 achievements in Into the Breach using Claude Code's computer use capability (screenshots + mouse/keyboard control). The game runs natively on macOS. The bot reads the screen to extract game state, reasons about optimal moves, and executes them via mouse clicks.

## Important Context

- Into the Breach is a turn-based tactics game on an 8x8 grid. It is fully deterministic with perfect information — every enemy telegraphs their attacks before you move.
- The ITB-ModLoader (Lua-based) only works on Windows. Since we're on Mac, we use **computer vision** to extract game state from screenshots and **mouse control** to execute moves. This is the correct approach for this platform.
- The game is turn-based with no time pressure (except one specific achievement). The bot can take as long as it needs per turn.
- Into the Breach is available on Steam. App ID: 590380.

## Architecture Overview

The system has 5 layers:

### Layer 0: Game Loop

`game_loop.py` CLI + `src/loop/` (session.py, logger.py, commands.py). Claude is the control loop; Python tools are stateless. Session management, phase detection, command dispatch, decision logging.

### Layer 1: State Extraction

Primary: save file parser (`src/capture/save_parser.py`) reads the game's Lua save files directly. Fallback: CV pipeline (`src/vision/`) for screens the save file cannot distinguish (shop, reward selection, menus).

### Layer 2: Game State Model

`src/model/` — Board, Unit, WeaponDef dataclasses. The Board is built from parsed save data and is the single source of truth the solver operates on.

### Layer 3: Solver

`src/solver/` — Constraint-based threat response followed by bounded search. Given a board with known enemy intents, finds the optimal sequence of mech actions. Evaluation function uses configurable `EvalWeights` so achievement targeting can bias scoring without changing the search logic.

### Layer 4: Achievement Strategist

`src/strategy/` — Selects which `EvalWeights` to inject into the solver based on the current achievement target. Manages run-level configuration: squad selection, island order, shop priorities, pilot choices.

### Execution Model: Claude as Controller

Claude operates as the outer control loop. Each Python CLI command (`game_loop.py read`, `solve`, `execute`, `verify`) is a stateless tool that reads state, computes, outputs, and exits. Claude calls these tools in sequence, interprets their output, executes mouse/keyboard actions via MCP, and decides what to do next. This inverts the traditional bot architecture: instead of a Python process driving the game, Claude drives the game and uses Python for computation. The session file (`sessions/active_session.json`) persists state between CLI calls.

Grid coordinate mapping uses the game's isometric projection: mcp_x = OX + 42*(save_x - save_y), mcp_y = OY + 25*(save_x + save_y), where OX/OY are derived from the game window position (auto-detected via Quartz CGWindowListCopyWindowInfo). Step sizes scale with window dimensions.

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

1. Always verify save file state after each mech execution.
2. Never execute mech N+1 before verifying mech N succeeded.
3. Click TILE CENTERS, not sprites. Sprites render 100-170px above tile center in MCP coords.
4. After every failed run, analyze the critical turn. Save snapshot first.
5. Select mechs by clicking their PORTRAIT, then clicking board to dismiss popup, then re-clicking portrait. Do NOT rely on Tab for non-consecutive execution.
6. Priority order — buildings > threats > kills > spawns.
7. Save file is the source of truth. Re-parse after every action.
8. Never move onto ACID tiles voluntarily (doubles damage, disables armor).
9. SELF-IMPROVEMENT — Every process error leads to an immediate CLAUDE.md update with a guard/fix to prevent recurrence. Every mistake makes the process permanently better.
10. Always use grid_to_mcp() for coordinates. MCP screenshot coords = Quartz logical coords (verified). grid_to_mcp() auto-detects window position via Quartz — no hardcoded offsets.
11. Arm weapons via keyboard: '1' for primary, '2' for secondary. Check which weapon the solver chose before pressing.
12. NEVER press Space (triggers End Turn dialog unexpectedly).
13. Use ALL mech actions every turn. Even suboptimal moves beat skipping.
14. Solver blind spots (temporary, until implemented): No repair action. No environment hazard awareness (air strikes, tidal waves, lightning). Check for these visually and override solver if needed.
15. On recovery from crash/timeout, ALWAYS start with cmd_read + cmd_solve. Never resume a previous solution — the board may have changed.
16. Save file (saveData.lua) only updates at TURN BOUNDARIES, not per-mech-action. bActive does NOT change until End Turn is pressed. Per-mech verification cannot use save file parsing — use visual confirmation or wait until after End Turn to verify.
17. Portrait clicks require clicking the portrait, then clicking the board to dismiss pilot popup, then re-clicking portrait. Use coordinates (win.x+65, win.y+Y) where Y is 250/310/365 for portraits 0/1/2. Always wait 2s after open_application before first click.
18. During deployment phase, the save file has iState=4 and no deployment zone data for most maps. Deploy by scanning for yellow arrow indicators on valid tiles. The deployment zone is computed by the game engine at runtime.

## Phase Protocols

### COMBAT_PLAYER_TURN

The main loop. Execute every turn in this exact sequence:

1. `game_loop.py read` — Confirm phase is COMBAT_PLAYER_TURN. Review board state, threats, active mechs.
2. `game_loop.py solve` — Get solution (N actions for N active mechs). If empty solution (timeout): take screenshot, play manually.
3. For each action i in 0..N-1:
   a. `game_loop.py execute i` — Get click plan for this mech.
   b. Execute clicks via computer-use MCP.
   c. Wait 2-3 seconds for animation.
   d. `game_loop.py verify` — Confirm mech acted (retries up to 5x at 1.5s intervals).
      - PASS: continue to next mech.
      - FAIL: retry execute once. If still fails, screenshot + diagnose.
   NOTE: Save file only updates after End Turn. Per-mech verify will always show 'still active'. Trust visual confirmation (dimmed portrait = mech acted) between individual mech actions. Only use save-file verify after end_turn.
4. `game_loop.py end_turn` — Click End Turn, wait for animations (minimum 6s).
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

1. Take screenshot — save file does not distinguish shop from map.
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
- **Save file not updating:** Retry verify up to 5x with 1.5s delay (7.5s max).
- **Grid power = 0:** Log game over, snapshot, analyze.
- **Crash/timeout:** Start fresh with `cmd_read` + `cmd_solve` (Rule 15). Never resume old solution.

## Game Loop Command Reference

All commands are subcommands of `game_loop.py`. Each is stateless: read state, compute, output, exit.

**State Reading:**
- `read` — Parse save file, detect phase, dump board state + threats + active mechs.
- `verify [index]` — Re-parse save, confirm mech acted. Retries up to 5x at 1.5s.
- `status` — Quick summary: turn, grid power, mech HP, threats, objectives.

**Combat:**
- `solve` — Run solver, store solution in session, output action sequence.
- `execute <index>` — Output click plan for action N from the active solution. Does NOT click.
- `end_turn` — Output click plan for End Turn button.

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
│   ├── capture/           # Screenshot and window detection
│   │   └── save_parser.py # Lua save file parser + phase detection
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

Phase 4 complete. Game loop CLI implemented. Claude-as-the-loop architecture operational.
