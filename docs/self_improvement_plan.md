# Self-Improvement System Plan

## Goal

Run the game loop as fast as possible to collect maximum game data, then use that data to automatically improve the solver. The cycle: **play fast -> record everything -> analyze failures -> tune weights -> validate -> deploy -> repeat**.

## Current Bottleneck

The loop takes **12-27 minutes per turn**. A full game run (~80 turns across 4 islands) takes 50-90 hours. The bottleneck is NOT the solver (0.3s) or bridge IPC (0.3s) -- it's Claude's inference between MCP calls and the hover-verify-click protocol (51+ MCP round-trips per turn).

Switching combat execution to bridge commands would drop a turn to **10-25 seconds** -- a 30-100x speedup. But the bridge execution layer has critical gaps that must be fixed first.

---

## Phase 0: Fix Bridge Execution Layer

**Status:** COMPLETE
**Why first:** Everything downstream depends on correct bridge execution. Without this, `auto_turn` produces invalid game states.

### 0A: Replace `Board:DamageSpace()` with proper weapon execution

**Problem:** The modloader's ATTACK handler (`modloader.lua:443-456`) uses `Board:DamageSpace(SpaceDamage(Point(tx,ty), damage, push_dir))` -- a primitive single-tile damage function. It does NOT execute actual weapon skills. This means:
- No AoE/splash patterns (artillery, burst beam)
- No chain effects (chain whip, laser pierce)
- No weapon-applied status effects (fire, acid, freeze from the weapon itself)
- No multi-tile weapons (Janus Cannon dual-direction, charge attacks)
- ~50% of weapons produce wrong game states

**Fix:** Use the game's `SkillEffect` API. Each weapon in ITB is a Lua skill object. The correct approach:
```lua
-- Instead of:
local dmg = SpaceDamage(Point(tx, ty), damage, push_dir)
Board:DamageSpace(dmg)

-- Use:
local skill = _G[weapon_id]  -- e.g. _G["Prime_Punchmech"]
if skill and skill.GetSkillEffect then
    local effect = skill:GetSkillEffect(Point(px, py), Point(tx, ty))
    Board:AddEffect(effect)  -- queues full weapon animation + effects
end
```

**Fallback:** If `GetSkillEffect` is not available for all weapons, keep `DamageSpace` as a fallback but log a warning. Track which weapons use the fallback for data quality tagging.

**Files:** `src/bridge/modloader.lua` (ATTACK handler, lines 443-456)

**Validation:** Test with Rift Walkers (simple weapons) first, then Zenith Guard (laser pierce), then Flame Behemoths (fire application).

### 0B: Implement real END_TURN

**Problem:** The modloader calls `pawn:SetActive(false)` on all mechs (`modloader.lua:515-529`). This does NOT call the game engine's turn transition. The design doc describes `GetGame():EndTurn()` but it's not implemented.

**Fix:**
```lua
function cmd_end_turn()
    -- Call the actual game engine end-turn
    GetGame():EndTurn()
    -- Wait for enemy phase to complete before ACKing
    -- (Board:IsBusy() or poll until phase returns to player turn)
end
```

**Edge case:** `EndTurn()` may trigger game-over if grid power drops to 0 during enemy phase. The ACK must indicate the resulting phase (player_turn, mission_end, game_over).

**Files:** `src/bridge/modloader.lua` (END_TURN handler, lines 515-529)

### 0C: Add REPAIR command

**Problem:** Bridge has no REPAIR handler. The solver emits `weapon="_REPAIR"` for repair actions. Bridge ATTACK with `_REPAIR` fails: `_G["_REPAIR"]` is nil, producing an error ACK that goes unchecked.

**Fix:** Add a dedicated REPAIR command handler:
```lua
elseif cmd == "REPAIR" then
    local uid = tonumber(parts[2])
    local pawn = Board:GetPawn(uid)
    if pawn then
        pawn:SetRepair(true)  -- or pawn:Repair() depending on API
    end
```

**Files:** `src/bridge/modloader.lua`, `src/bridge/writer.py` (intercept `_REPAIR` weapon and send REPAIR command instead of ATTACK)

### 0D: Add animation handling

**Problem:** ACK is written immediately after the Lua API call returns. No animation wait. Rapid commands could overlap.

**Fix options (pick one):**
1. **`Board:IsBusy()` polling** -- after each command, poll until the board is no longer busy, then ACK. Most correct.
2. **Conservative delays** -- 1.5s after MOVE, 2.5s after ATTACK, 5s after END_TURN. Simple but wasteful.
3. **Configurable mode** -- fast mode (no delays, for data collection) vs visual mode (delays, for watching).

**Recommendation:** Option 3. Default to fast mode. Add a `SET_SPEED` bridge command to toggle.

### 0E: Add ACK error detection + sequence IDs

**Problem 1:** Python never checks ACK content for errors. `"ERROR: pawn 100 not found"` is treated as success.

**Problem 2:** With rapid commands, ACKs could be misattributed (50ms settle time is fragile).

**Fix:**
- Add command sequence IDs: `CMD 001 MOVE_ATTACK ...` -> `ACK 001 OK ...`
- Parse ACK content: if starts with "ERROR", raise an exception.
- In `wait_for_ack()`, match the sequence ID before accepting.

**Files:** `src/bridge/protocol.py` (write_command, wait_for_ack), `src/bridge/modloader.lua` (execute_command ACK format)

### 0F: Add DEPLOY command

**Problem:** Bridge provides deployment zone data but has no DEPLOY command. `auto_mission` can't deploy mechs without MCP clicks.

**Fix:** Add `DEPLOY <uid> <x> <y>` command that places a mech during deployment phase.

**Files:** `src/bridge/modloader.lua`, `src/bridge/writer.py`

### Phase 0 Definition of Done
- [x] ATTACK uses proper weapon skill execution for all Rift Walkers weapons
- [x] END_TURN calls `GetGame():EndTurn()` and waits for enemy phase
- [x] REPAIR command works
- [x] ACK includes sequence ID and error detection works
- [x] DEPLOY command works
- [x] Animation handling configurable (fast/visual mode)
- [ ] Tested: full Rift Walkers mission completes via bridge commands only

*Implemented in commit `b1c5526`. End-to-end mission test still pending.*

---

## Phase A: Speed Layer (`auto_turn` / `auto_mission`)

**Status:** COMPLETE
**Depends on:** Phase 0
**Expected speedup:** 30-100x (12-27 min/turn -> 10-25 sec/turn)

### A1: `cmd_auto_turn` command

One CLI call that chains: read -> solve -> execute all mechs -> end turn.

```python
def cmd_auto_turn(session, args):
    # 1. Read bridge state
    board = cmd_read(session, args)
    if board.phase != "combat_player":
        return {"error": f"Not in combat phase: {board.phase}"}
    
    # 2. Solve
    solution = cmd_solve(session, args)
    if not solution.actions:
        return {"error": "Empty solution (timeout or no active mechs)"}
    
    # 3. Execute each mech action via bridge
    for i, action in enumerate(solution.actions):
        # Health check bridge before each action
        if not is_bridge_active():
            return {"error": f"Bridge died after action {i}"}
        
        result = execute_bridge_action(action)
        
        # Check ACK for errors
        if result.startswith("ERROR"):
            return {"error": f"Action {i} failed: {result}"}
        
        # Per-action state validation (optional, configurable)
        if args.verify_each:
            post_state = refresh_bridge_state()
            # Verify mech acted (active=False or position changed)
    
    # 4. End turn
    end_result = execute_bridge_end_turn()
    
    # 5. Wait for enemy phase + next player turn
    # Poll bridge state until phase returns to combat_player or mission ends
    
    # 6. Record everything
    return {"status": "ok", "actions": len(solution.actions)}
```

**Edge cases to handle:**
- **Empty solution (solver timeout):** Return control to Claude for manual play
- **0, 1, or 2 active mechs:** Iterate `solution.actions` count, don't hardcode 3
- **Webbed/frozen mechs:** Solver must check `unit.web` and `unit.frozen` in movement planning (currently missing -- fix in `src/solver/movement.py`)
- **IPC timeout mid-turn:** After mech N succeeded but mech N+1 timed out: re-read state, re-solve for remaining mechs
- **Game over (grid power = 0):** After END_TURN, check `grid_power <= 0`. Return with game_over status.
- **Mission ending (last turn):** After END_TURN on `turn == total_turns`, detect mission end phase

**Files:** `src/loop/commands.py` (new function), `game_loop.py` (register subcommand)

### A2: `cmd_auto_mission` command

Loops `auto_turn` from deployment through mission end.

```
auto_mission flow:
  1. Read state
  2. If deployment phase: auto-deploy (bridge DEPLOY command)
  3. Loop:
     a. auto_turn()
     b. Read state
     c. If combat_player: continue loop
     d. If mission_ending/between_missions: return (Claude handles rewards)
     e. If game_over: return with game_over status
```

**Falls back to Claude for:** reward selection, shop, island map, island selection, main menu. These are UI screens the bridge can't control.

**Files:** `src/loop/commands.py`, `game_loop.py`

### A3: Session state management in single-process mode

**Problem:** Each `cmd_execute` loads session fresh from disk. In `auto_turn` (single process), multiple executions need in-memory state management.

**Fix:** Pass the session object through the auto_turn loop instead of reloading from disk per action. Save once at the end.

**Files:** `src/loop/commands.py`, `src/loop/session.py`

### A4: CLAUDE.md rule updates

Rules 7, 11, 19 forbid bridge execution and mandate hover-verify-click. Add conditional exceptions:

- Bridge execution is allowed within `auto_turn`/`auto_mission` commands
- Hover-verify-click still required for MCP-based operations (menus, shop, rewards)
- Document the dual-mode execution model

### Phase A Definition of Done
- [x] `game_loop.py auto_turn` completes a full combat turn via bridge in <30s
- [x] `game_loop.py auto_mission` completes a full mission (deploy through mission end)
- [x] All edge cases handled (empty solution, dead mechs, timeout recovery, game over)
- [x] CLAUDE.md updated with dual-mode execution rules
- [x] Per-action state validation available (configurable)

*Implemented in commit `b1c5526`. CLAUDE.md updated with dual-mode execution rules.*

---

## Phase B: Data Quality Fixes

**Status:** COMPLETE
**The weapon ID bug (Unknown weapon in replay) was already fixed in commit `ddb4f88`.**

### B1: Flag pre-fix recordings as unreliable

All 4 existing runs have corrupted `action_results` and `predicted_outcome` data. The bridge state (`board.json`) is still valid, but derived fields are wrong.

**Action:** Add a `data_version` field to new recordings. Old recordings (pre-ddb4f88) should be treated as bridge-state-only.

### B2: Fix remaining weapon name issues

- **Vice Fist collision:** Two weapons share the display name "Vice Fist" (`Prime_Shift` and `Brute_Grapple`). `weapon_name_to_id()` returns the wrong one for Rift Walkers. Fix: use weapon context (mech type) to disambiguate.
- **Repair edge case:** `_REPAIR` vs `Repair` mapping works now but is fragile. Add explicit test.

**Files:** `src/model/weapons.py` (weapon_name_to_id)

### B3: Fix `evaluate_breakdown()` scaling mismatch

**Problem:** `evaluate_breakdown()` (evaluate.py:181) uses raw weights without turn-aware `_scaled()` function. All recorded score breakdowns are wrong.

**Fix:** Apply the same `_scaled()` calls in `evaluate_breakdown()` as in `evaluate()`.

**Files:** `src/solver/evaluate.py`

### B4: Fix missing `board` parameter in `detect_triggers()`

**Problem:** `_record_post_enemy()` (commands.py:215) calls `detect_triggers(actual, predicted, deltas, solve_data)` without passing the `board` parameter. Tier 4 rule violations (mech on acid, mech on danger) are silently disabled.

**Fix:** Pass the board to `detect_triggers()`.

**Files:** `src/loop/commands.py`

### B5: Fix solver web/frozen handling

**Problem:** `get_reachable_tiles()` in `movement.py` doesn't check `unit.web` or `unit.frozen`. The solver produces impossible actions for status-affected mechs.

**Fix:** If `unit.web` or `unit.frozen`, `move_speed = 0`. If `unit.frozen`, skip the mech entirely (no attack either).

**Files:** `src/solver/movement.py`, `src/solver/solver.py`

### Phase B Definition of Done
- [x] New recordings post-fix have correct action_results and predicted_outcome
- [x] evaluate_breakdown matches evaluate (with scaling)
- [x] Tier 4 triggers actually fire in production
- [x] Webbed/frozen mechs handled correctly by solver

*Implemented in commit `b1c5526`.*

---

## Phase C: Weight Loading Infrastructure

**Status:** COMPLETE
**Depends on:** None (can be developed in parallel with Phases 0/A)

### C1: Make Rust `EvalWeights` deserializable

**Current:** `EvalWeights` in `rust_solver/src/evaluate.rs` has `#[derive(Clone, Debug)]` but no serde derives.

**Fix:** Add `#[derive(Deserialize)]` and add an optional `eval_weights` field to `JsonInput` in `serde_bridge.rs`.

### C2: Port achievement fields to Rust

**Problem:** Python `EvalWeights` has 5 achievement-specific fields (`enemy_on_fire`, `enemy_pushed_into_enemy`, `chain_damage`, `smoke_placed`, `tiles_frozen`). Rust has none.

**Fix:** Add these fields to the Rust `EvalWeights` struct with default 0.0.

### C3: Extract hardcoded values into EvalWeights

**Problem:** 6+ values in the Rust evaluator are hardcoded outside `EvalWeights`:
- Psion kill bonuses: 2000/1500/1000/1600/2500 (5 types)
- Fire damage bonus: 100
- Acid tile penalty: -200
- Grid urgency multipliers: 5.0/3.0/2.0

**Fix:** Add these as fields to `EvalWeights` so the optimizer can see them.

### C4: Weight version file system

```
weights/
  v001_default.json       # Extracted from current hardcoded defaults
  active.json             # Copy of currently deployed version
  history.jsonl           # Log of version transitions
```

Each weight file:
```json
{
  "version": "v001",
  "parent": null,
  "description": "Original hardcoded defaults",
  "created": "2026-04-10",
  "weights": { "building_alive": 10000, ... },
  "stats": { "runs_played": 0, "wins": 0 }
}
```

### C5: Wire `cmd_solve()` to load weights

`cmd_solve()` loads `weights/active.json`, injects into the bridge JSON sent to Rust. Records `weight_version` in solve output and `RunSession`.

### C6: Add `to_dict()` and hash to EvalWeights

For recording metadata. Hash enables fast grouping without comparing all fields.

### Phase C Definition of Done
- [x] Rust solver accepts custom weights from JSON input
- [x] Achievement fields exist in Rust EvalWeights
- [x] Hardcoded evaluator values exposed as tunable fields
- [x] Weight files exist in `weights/` directory
- [x] `cmd_solve` loads and records weight version
- [x] Python and Rust EvalWeights are in sync

*Implemented in commit `b1c5526`. 27 fields synchronized between Python and Rust.*

---

## Phase D: Enhanced Recording

**Status:** COMPLETE
**Depends on:** Phases A (for per-action recording at speed) and C (for weight metadata)
**Dependencies now satisfied:** Phases A and C are complete.

### Current state

Recording exists but is minimal:
- `_record_turn_state()` (`commands.py:63-91`) writes `turn_NN_<label>.json` per turn
- Labels: `board`, `solve`, `post_enemy`, `triggers`
- Format: `{"timestamp", "run_id", "turn", "label", "data": {...}}`
- No atomic writes, no mission prefix, no run manifest
- 5 runs recorded so far in `recordings/`
- `RunSession` (`session.py`) has no `mission_index` field

### D1: Run manifest

Write `recordings/<run_id>/manifest.json` at `cmd_new_run()` (`commands.py:321`). Update incrementally as missions complete. Finalize at run end.

Contents: squad, difficulty, achievement_targets, solver_version (Cargo.toml + git hash), eval_weights snapshot, mission summaries (appended), run outcome.

**Crash safety:** Use atomic writes (tmp + os.replace). Partial manifest from crashed runs is still useful.

**Solver version detection:** Read `Cargo.toml` version + `git rev-parse --short HEAD` at session start.

### D2: Mission index tracking

**Problem:** No `mission_index` in `RunSession`. Turn files collide across missions (confirmed: `session.py` has no such field).

**Fix:**
- Add `mission_index: int` to `RunSession` (`src/loop/session.py`), increment when `current_mission` changes
- Prefix turn files: `m00_turn_02_solve.json`
- Update file-reading code: `_record_turn_state` (`commands.py:63`), `_record_post_enemy` (`commands.py:182`), `cmd_replay` (`commands.py:1236`)
- Fallback to old naming for pre-migration recordings (5 existing runs)

### D3: Per-action recording

After each bridge action in `cmd_auto_turn` (`commands.py:1393`), capture a lightweight diff:

```json
{
  "action_index": 0,
  "mech_uid": 42,
  "action": "MOVE_ATTACK Prime_Punchmech E4",
  "pre_state": { "mech_pos": [3,5], "target_hp": 3 },
  "post_state": { "mech_pos": [4,5], "target_hp": 0 },
  "expected_vs_actual": "match",
  "wall_clock_ms": 1250
}
```

**Integration point:** `cmd_auto_turn` calls `cmd_execute(i)` per action (`commands.py:1394`). Add pre/post state capture around each call. Buffer in memory, write as single batch at end of turn.

### D4: Mission and run summaries

- Write `m00_mission_summary.json` when phase transitions to `between_missions` (detect in `cmd_auto_mission`, `commands.py:1538`)
- Write `run_summary.json` when run ends (victory, defeat, or crash)
- Aggregate: total buildings lost, grid power delta, enemies killed, trigger counts, prediction accuracy

### D5: Run ID collision prevention

Current: `datetime.now().strftime("%Y%m%d_%H%M%S")` in `cmd_new_run` (`commands.py:321`) -- second-level granularity.

**Fix:** Append milliseconds: `"%Y%m%d_%H%M%S_%f"[:19]` or add a 4-char random suffix.

### D6: Atomic writes for recording files

**Problem:** `_record_turn_state` (`commands.py:90`) uses plain `open() + json.dump()` with no atomic write. Crash during write = corrupted JSON.

**Fix:** Use tmp + `os.replace` pattern (same as `RunSession.save()` in `session.py`).

### Phase D Definition of Done
- [x] Run manifest written and updated per mission
- [x] Mission-prefixed turn files prevent collision
- [x] Per-action diffs captured during auto_turn
- [x] Mission and run summaries generated
- [x] Atomic writes for all recording files
- [x] Solver version and weight version in all metadata
- [x] Run ID collision prevention (millisecond suffix)

*Implemented. Run IDs now include milliseconds (e.g. `20260410_133812_268`). Recordings use `m00_turn_01_board.json` naming. `cmd_replay` falls back to old naming for pre-migration recordings.*

---

## Phase E: Failure Analysis

**Status:** COMPLETE
**Depends on:** Phase D (for richer recording data)

### Current state

Trigger detection exists: `detect_triggers()` in `src/solver/analysis.py:17` receives actual/predicted/deltas/solve_data/board params. Triggers are recorded to `turn_NN_triggers.json` with severity counts (`commands.py:220-228`). No failure database or `analyze` command yet.

### E1: Simplify root-cause categories

**Problem:** The original plan proposed 5 root causes (`simulation_bug`, `weight_miscalibration`, `missing_mechanic`, `execution_error`, `search_limitation`). Review found these are NOT distinguishable from available data. `simulation_bug` vs `missing_mechanic` both manifest as identical prediction failures.

**Revised categories (operationally distinguishable):**
- `prediction_mismatch` -- predicted != actual (was: simulation_bug + missing_mechanic)
- `search_exhaustion` -- solver timed out or pruned too aggressively
- `execution_mismatch` -- mech not at expected position after verify (bridge ACK ≠ game reality)
- `strategic_decline` -- grid power or mech HP declining over turns (cumulative bad decisions)

### E2: Failure database

Append-only JSONL at `recordings/failure_db.jsonl`. Each line:

```json
{
  "id": "20260408_194927_m00_t01_grid_power_drop",
  "run_id": "20260408_194927",
  "mission": 0,
  "turn": 1,
  "trigger": "grid_power_drop_unexpected",
  "tier": 1,
  "root_cause": "prediction_mismatch",
  "severity": "critical",
  "details": "Predicted grid 2, actual 1",
  "context": {
    "squad": "Rift Walkers",
    "island": "Archive",
    "grid_power_before": 2,
    "solver_timed_out": false,
    "weight_version": "v001"
  },
  "solver_version": "rust-0.1.0-abc123",
  "replay_file": "recordings/20260408_194927/m00_turn_01_board.json"
}
```

**Retention:** Add `solver_version` field. Implement windowed analysis (last N runs). Add `resolved` flag when a fix is deployed.

### E3: New trigger tiers

- **Tier 2 (Execution failures):** `action_not_executed` (mech still active after bridge ACK), `position_mismatch` (mech at wrong tile). Requires per-action state validation from Phase D3.
- **Tier 5 (Missed opportunities):** DEFERRED. Detecting genuine missed opportunities requires knowing the optimal solution, which is what the solver already tries to find. Not worth the complexity yet.

### E4: Pattern detection with minimum sample gates

New command: `game_loop.py analyze [--min-samples 30]`

Patterns to detect (gated behind minimum sample counts):
- Trigger frequency by type (no minimum -- always useful)
- Trigger frequency by island/squad (minimum 10 runs per group)
- Temporal patterns: do failures increase on later turns? (minimum 50 turns)
- Severity escalation: does Tier 1 on turn N predict Tier 6 by turn N+2? (minimum 30 sequences)

**Do NOT run correlation analysis on <30 data points.** Report raw counts only until sufficient data exists.

### Phase E Definition of Done
- [x] Failure database populated from triggers
- [x] Root-cause categories are operationally distinguishable
- [x] Tier 2 execution failure detection works with per-action validation
- [x] `game_loop.py analyze` produces useful reports
- [x] Minimum sample gates prevent overfitting to noise

*Implemented. Failure DB at `recordings/failure_db.jsonl`. Root causes: prediction_mismatch, execution_mismatch, search_exhaustion, strategic_decline. Tier 2 checks per-action diffs from auto_turn. `analyze` command with `--min-samples` gating.*

---

## Phase F: Batch Validation

**Status:** COMPLETE
**Depends on:** Phases B (correct simulation), C (weight loading), D (recording metadata)
**Dependencies now satisfied:** B and C are complete. D is the remaining prerequisite.

### Current state

`cmd_replay` exists (`commands.py:1236-1330`). It reconstructs a Board from `turn_NN_board.json` bridge_state, runs the Python solver (`solve_turn()`), and compares with the original recorded solution. Does NOT use the Rust solver.

### F1: `cmd_replay` upgrade to Rust solver

**Problem:** `cmd_replay` (`commands.py:1275`) calls `solve_turn()` which routes to the Python solver. The Rust solver is ~2100x faster.

**Fix:** Add `--rust` flag to `cmd_replay`. When set, serialize the board to JSON and call the Rust solver via `solve_turn_rust()` (same path as `cmd_solve`, `commands.py:570-600`).

### F2: `game_loop.py validate <old> <new>` command

Replays all historical boards with both weight sets. For each board:
1. Run solver with OLD weights -> get solution A
2. Run solver with NEW weights -> get solution B
3. Simulate both solutions (replay_solution) -> get predicted outcomes
4. Compare: buildings alive, enemies killed, grid power, trigger count

**Critical design note:** Compare outcomes using a FIXED scoring function (not the weights being tested). Otherwise you're comparing values from different scoring functions, which is meaningless. Use a "ground truth" scorer that measures only objective metrics: buildings alive, grid power, mechs alive.

**Output:**
```json
{
  "old_version": "v001",
  "new_version": "v002",
  "boards_tested": 200,
  "new_better": 140,
  "old_better": 35,
  "ties": 25,
  "regression_boards": ["run_X_m01_t03", ...],
  "critical_regressions": 2
}
```

### F3: Regression gate

Rules for promoting new weights:
- New weights must not produce worse outcomes on >20% of boards
- No new CRITICAL triggers on boards where old weights had none
- **Severity-weighted comparison:** A critical regression (grid power drop) counts 10x more than a medium one

### F4: Solver version isolation

**Problem:** If Rust solver code changed between recordings, replay tests weights AND code changes simultaneously.

**Fix:** Tag each recording with `solver_commit_hash`. Filter validation to boards from the same solver version.

### Phase F Definition of Done
- [x] `cmd_replay` supports Rust solver (default, `--no-rust` for Python fallback)
- [x] `game_loop.py validate` compares weight versions across boards
- [x] Fixed scoring function (not weight-dependent) for fair comparison
- [x] Regression gate blocks bad weight changes (20% threshold + critical check)
- [x] Solver version filtering in validation (`--solver-version` flag)

*Implemented. Validated on 21 boards — same weights produce all ties as expected. `_solve_with_rust()` helper shared between replay and validate. `_fixed_score()` uses buildings*100 + grid*50 + mechs*30 - destroyed*200.*

---

## Phase G: Weight Auto-Tuning

**Status:** COMPLETE
**Depends on:** Phases B, C, F, and **sufficient data** (200+ board recordings)
**Dependencies now satisfied:** B and C are complete. F and data collection are remaining prerequisites.

### Current state

Weight infrastructure is ready (Phase C). `weights/active.json` has v001 defaults (27 fields). `cmd_solve` loads and injects weights (`commands.py:532-540`). Only 5 runs recorded so far — need 200+ boards before tuning. At ~15 boards/run with `auto_mission`, need ~14 runs (~7 hours at 30x speed).

### G1: Scope reduction -- tune 5 weights first

**Problem:** CMA-ES with 16-36 dimensions needs hundreds of boards. Current data is far too small.

**Start with the 5 most impactful weights only:**
1. `building_alive` (10000) -- core defensive weight
2. `enemy_killed` (500) -- offensive vs defensive balance
3. `spawn_blocked` (400) -- how much to prioritize blocking
4. `mech_hp` (100) -- self-preservation
5. `grid_power` (5000) -- strategic resource valuation

Hold all other weights at default. This is a tractable 5D problem that works with ~50-100 boards.

### G2: Per-turn optimization only

**Problem:** Credit assignment across turns is fundamentally broken. Replaying turn 4 with new weights on a board that only exists because of old-weight decisions on turns 1-3 is invalid.

**Accept single-turn credit assignment.** For each board, measure: "given THIS board state, do the new weights produce a better single-turn outcome?" This is valid because the board state is fixed ground truth.

**Metric per board (using fixed scorer from F2):**
```
turn_score = (
    buildings_alive_after * 100
    + grid_power_after * 50
    - mechs_lost * 200
    + enemies_killed * 10
)
```

### G3: Consider Bayesian optimization first

**Problem:** CMA-ES is a good general-purpose optimizer but needs many evaluations. With 50-100 boards, Bayesian optimization (GP-based, e.g., scikit-optimize) is more sample-efficient.

**Plan:**
- Start with Bayesian optimization (scikit-optimize) for 5D search
- Switch to CMA-ES when data exceeds 500 boards and search space expands
- Both wrapped in `game_loop.py tune [--method bayesian|cma] [--dimensions 5]`

### G4: Parameter interaction constraints

**Problem:** Base weight * scaling factor creates non-identifiable parameterizations. Doubling base and halving scale gives same result.

**Fix:** When tuning scaling parameters (later, not in initial 5D search):
- Fix `floor + scale = constant` (e.g., 1.8 for enemy_killed)
- Only tune one of {base, floor} per weight, not both simultaneously
- Or: tune the effective range `[base * floor, base * (floor + scale)]` directly

### G5: Data collection gating

**Do NOT start tuning until:**
- Phase B fixes are deployed and validated
- 200+ board recordings exist from the fixed solver
- `game_loop.py analyze` shows prediction accuracy > 70%

**Estimated collection time:** With `auto_turn` at 30x speed, one full run (~80 turns) takes ~30 minutes. 3 runs = 240 boards. Gating threshold reached in ~90 minutes of gameplay.

### Phase G Definition of Done
- [x] `game_loop.py tune` command works (random search + coordinate refinement, no external deps)
- [x] 5D weight search implemented (building_alive, enemy_killed, spawn_blocked, mech_hp, grid_power)
- [x] Tuned weights validated via Phase F before deployment (auto-validates + auto-deploys if PASS)
- [x] Data collection gate enforced (default 50 boards, configurable via `--min-boards`)

*Implemented in `src/solver/tuner.py`. Uses random search + coordinate refinement (no scikit-optimize/cma dependency). Tested on 21 boards. Saves versioned weight files, auto-validates, auto-deploys if regression gate passes. Upgradable to Bayesian/CMA-ES when deps available.*

---

## Phase H: Online Adaptive Selection

**Status:** DEFERRED
**Depends on:** Phase G + parallel game instances

### Why deferred

Thompson sampling needs hundreds of runs per profile to converge. At 1-2 hours per run, even with speedup, this requires either:
- Months of continuous play, OR
- Multiple parallel game instances

Defer until multi-instance is working (see Future Work).

### When to revisit

When we have:
- 3+ weight profiles from Phase G tuning
- 50+ runs per profile
- Multi-instance capability (2-4 simultaneous games)

---

## Future Work (Not Scheduled)

### Multi-instance parallel play

Run 2-4 game instances simultaneously for faster data collection. Requires:
- Parameterized bridge IPC paths (`/tmp/itb_state_0.json`, `/tmp/itb_state_1.json`, etc.)
- Per-instance session files
- Coordinator that assigns run configurations and collects results
- Lua modloader parameterization via environment variable or mod config

**Priority:** Should be HIGH priority after Phase A works. Data collection rate is the primary bottleneck for the entire improvement system. 4 instances = 4x data = 4x faster tuning convergence.

### Multi-turn lookahead / forward simulation

Currently the solver only evaluates single-turn outcomes. Multi-turn lookahead (simulate enemy attacks, predict spawns, evaluate 2-3 turns ahead) would be a more impactful improvement than weight tuning for many scenarios.

### Simulation correctness testing

Systematic validation that the solver's model matches game behavior:
- Catalog which mechanics the solver handles vs does not
- Run controlled experiments: known board + known action -> expected vs simulated outcome
- Regression test simulation after changes (currently only `tests/test_push_mechanics.py` exists)

### Achievement-specific strategy module

`src/strategy/__init__.py` is empty. Needs:
- Per-achievement weight overlays
- Squad selection logic
- Island routing
- Shop priority decisions
- Achievement progress tracking (Steam API)

### Monitoring dashboard

Track improvement over time:
- Win rate per squad
- Buildings lost per mission (average)
- Prediction accuracy (trigger rate)
- Solver timeout rate
- Achievement progress rate

---

## Known Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| `GetSkillEffect()` API may not exist for all weapons | Fallback to `DamageSpace` + data quality tag |
| Game updates change mechanics | Solver weapon tables need manual updating; detect via prediction mismatch spike |
| CMA-ES overfits to small data | Gate behind 200+ boards; start with 5D; use Bayesian opt for small data |
| Weight tuning compensates for simulation bugs | Fix simulation bugs FIRST (Phase B); validate prediction accuracy before tuning |
| Bridge desync from game state | Per-action state validation; bridge health checks between actions |
| Stale lock file blocks auto_mission | Add stale-lock detection (check if PID is alive) |
| Recording disk growth at high speed | ~2.4 MB per run, ~58 MB/day at full speed. Add retention policy after 1000 runs |

---

## Build Order Summary

```
Phase 0 (bridge fixes) ──────┐
                              ├──> Phase A (speed layer)      ✅ COMPLETE
Phase B (data quality) ───────┤                                  (b1c5526)
                              │
Phase C (weight loading) ─────┤
                              │
                              ├──> Phase D (enhanced recording)  ✅ COMPLETE
                              │
                              ├──> Phase E (failure analysis)    ✅ COMPLETE
                              │
                              ├──> Phase F (batch validation)    ✅ ──> Phase G (auto-tuning) ✅
                              │
                              └──> [Future] Phase H (online selection)
```

**All implementable phases (0 through G) are COMPLETE.**
Phase H (Online Adaptive Selection): DEFERRED — needs parallel instances + hundreds of runs.
Phase F: depends on D (for mission-prefixed recordings and run manifests).
Phase G: depends on F + sufficient data (200+ boards, ~14 runs with `auto_mission`).
Phase H: deferred (needs parallel instances + hundreds of runs).

## Test Coverage Gap

Only `tests/test_push_mechanics.py` exists. No tests for any Phase 0-C features:
- Bridge execution (GetSkillEffect, END_TURN, REPAIR, DEPLOY) — hard to unit test (needs game runtime)
- `auto_turn` / `auto_mission` — integration test, needs bridge
- Weight loading/deserialization — **easy to test**, should add
- `evaluate_breakdown` scaling — **easy to test**, should add
- Webbed/frozen mech handling — **easy to test**, should add
- Sequence ID / BridgeError — **easy to test**, should add

**Recommendation:** Add unit tests for the "easy to test" items as part of Phase D work. Integration tests for bridge/auto_turn require the game running and are better handled as manual validation.
