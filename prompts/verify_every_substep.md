# Task: Implement verify-after-every-sub-action solver feedback loop

## Problem

The Into the Breach bot's solver plans all 3 mech actions at the start of each turn based on a single board snapshot, then executes them all without checking if each action produced the expected result. When the solver's simulation is wrong (push goes wrong direction, damage amount is off, unit doesn't die), every subsequent action is planned against a now-incorrect board — cascading into building losses and game-overs.

The grid_power prediction is consistently wrong: the solver predicts grid_power=3 but actual is grid_power=1. This means the solver's internal simulation diverges from reality, and we never catch it until it's too late.

## Goal

Rewrite the turn execution flow so the solver gets **fresh board state after every sub-action** (move and attack are separate sub-actions). For 3 mechs, that's 6 board reads and 6 verifications per turn:

```
read board → solve all 3 actions →

MECH 1:
  execute MOVE → read board → diff against solver's predicted post-move state →
    MATCH: continue to attack
    MISMATCH: re-solve from actual board state (mech 1 has moved but not attacked, mechs 2+3 haven't acted)
  execute ATTACK → read board → diff against solver's predicted post-attack state →
    MATCH: continue to mech 2
    MISMATCH: re-solve from actual board state (mech 1 done, mechs 2+3 haven't acted)

MECH 2:
  execute MOVE → read board → diff → match/re-solve
  execute ATTACK → read board → diff → match/re-solve

MECH 3:
  execute MOVE → read board → diff → match/re-solve
  execute ATTACK → read board → diff → match/re-solve

end turn
```

Every desync feeds into the failure_db AND triggers an immediate re-solve with the actual board state. This makes every solver prediction verifiable and every mistake correctable within the same turn.

## Current Architecture (read these files first)

### Key files to understand before changing anything:

1. **CLAUDE.md** — Full operational manual. Read the entire thing. Pay special attention to:
   - Rule 14 (env_danger), Rule 16 (save file timing), Rule 20 (trust the solver)
   - Phase Protocols section (COMBAT_PLAYER_TURN flow)
   - Game Loop Command Reference
   - The "Execution Model: Claude as Controller" section

2. **src/loop/commands.py** — All CLI commands. Key functions:
   - `cmd_auto_turn()` — current auto_turn implementation (read→solve→execute all→end turn)
   - `cmd_solve()` — runs solver, stores solution in session, records predicted_states
   - `cmd_verify_action()` — diffs predicted vs actual per-action (currently post-action only)
   - `cmd_click_action()` — generates MCP click plan for one action (separates move from attack as separate clicks)

3. **src/bridge/writer.py** — writes bridge commands (execute, move, attack)
4. **src/bridge/reader.py** + **src/bridge/protocol.py** — reads bridge state from /tmp/itb_state.json
5. **src/bridge/modloader.lua** — Lua bridge inside the game. Writes state, reads commands.
6. **src/model/board.py** — Board dataclass, `Board.from_bridge_data()`
7. **rust_solver/src/solver.rs** — Rust solver search (the actual solver used in play)
8. **rust_solver/src/serde_bridge.rs** — Rust solver JSON input parsing
9. **sessions/active_session.json** — persistent session state between CLI calls

### Current execution flow (what needs to change):

**auto_turn (bridge speed mode):**
```python
board = read_bridge_state()           # ONE read
solution = solve(board)               # ONE solve for all mechs
for action in solution:
    bridge_execute(action)            # atomic move+attack, NO re-read
bridge_end_turn()                     # end turn
```

**manual play (MCP clicks):**
```
Claude calls: read → solve → click_action 0 → verify_action 0 → click_action 1 → verify_action 1 → ...
```
verify_action currently diffs the COMBINED move+attack result, not move and attack separately.

### What the solver outputs:

Each action in the solution has:
- `mech_uid`: which mech
- `move_to`: [x, y] destination tile
- `weapon`: weapon ID string
- `target`: [x, y] attack target
- `predicted_states`: per-action board snapshot (post move+attack combined)

The solver's internal search simulates each action on a board copy: apply move, apply weapon effect (damage, push, etc.), then check the resulting board. These intermediate states exist inside the Rust solver but are NOT currently exposed as separate post-move and post-attack snapshots.

## What Needs to Change

### 1. Solver: emit post-move AND post-attack predicted states

The Rust solver (`rust_solver/src/solver.rs`) currently captures one `predicted_state` per action (the final state after both move and attack). Change this to emit TWO predicted states per action:
- `predicted_post_move`: board state after the mech moves but before it attacks
- `predicted_post_attack`: board state after the mech attacks

These flow through `serde_bridge.rs` serialization back to Python.

### 2. Bridge: support separate MOVE and ATTACK commands

Currently `src/bridge/writer.py` sends a single `execute` command that does move+attack atomically. The Lua bridge (`modloader.lua`) handles this as one operation. Split into:
- `move <mech_uid> <dest_x> <dest_y>` — move only
- `attack <mech_uid> <weapon_slot> <target_x> <target_y>` — attack only

The Lua bridge needs corresponding handlers that call `pawn:Move(point)` and `pawn:FireWeapon(target, slot)` separately. After each, the bridge should auto-dump fresh state to `/tmp/itb_state.json`.

### 3. auto_turn: verify-and-re-solve loop

Rewrite `cmd_auto_turn()` in `src/loop/commands.py`:

```python
def cmd_auto_turn():
    board, raw = read_bridge_state()
    solution = solve(board)
    
    for i, action in enumerate(solution.actions):
        # --- MOVE PHASE ---
        bridge_move(action.mech_uid, action.move_to)
        actual_board = read_bridge_state()
        
        diff = compare(solution.predicted_post_move[i], actual_board)
        if diff:
            log_desync("move", i, diff)  # feed failure_db
            # Re-solve with actual board state
            # Mark mech i as "moved but not attacked"
            # Mark mechs 0..i-1 as "done"
            # Mark mechs i+1..N as "active"
            solution = re_solve(actual_board, acted=0..i-1, mid_action=i)
            action = solution.actions[0]  # first action is now for mech i's attack
        
        # --- ATTACK PHASE ---
        bridge_attack(action.mech_uid, action.weapon_slot, action.target)
        actual_board = read_bridge_state()
        
        diff = compare(solution.predicted_post_attack[i], actual_board)
        if diff:
            log_desync("attack", i, diff)
            # Re-solve with actual board for remaining mechs
            solution = re_solve(actual_board, acted=0..i)
    
    end_turn()
```

### 4. Manual play: same loop but with MCP clicks

The `click_action` command already separates move clicks from attack clicks. The flow becomes:
- `click_action <i> move` — emit just the select+move clicks
- Read board state
- Verify post-move
- `click_action <i> attack` — emit just the weapon+target clicks
- Read board state  
- Verify post-attack
- If desync: re-solve and update the remaining click plans

### 5. Solver: support partial-turn re-solving

The Rust solver needs to handle three mech states:
- **DONE**: already acted this turn (move+attack committed). Don't generate actions.
- **MID_ACTION**: has moved but not yet attacked. Generate attack-only actions (weapon+target, no move).
- **ACTIVE**: hasn't acted yet. Generate full move+attack actions.

Currently it only distinguishes ACTIVE vs DONE. Adding MID_ACTION requires:
- A new field in the solver input: `mechs[i].can_move = false` (for mid-action mechs)
- The solver skips move enumeration for that mech and only generates weapon/target options from its current position

### 6. Update CLAUDE.md

Rewrite rule 7 (manual play flow), rule 11 (mouse clicks only), the COMBAT_PLAYER_TURN phase protocol, and the command reference to reflect the new verify-after-every-sub-action flow.

### 7. Update verify_action

The existing `cmd_verify_action()` does post-action diffs. Refactor it into:
- `verify_move(action_index)` — diff post-move predicted vs actual
- `verify_attack(action_index)` — diff post-attack predicted vs actual
Both write to failure_db.jsonl with the diff details.

## Key Constraints

- **The bridge auto-dumps state** after each command via `write_atomic()` at the end of `dump_state()` in modloader.lua. Make sure both `move` and `attack` commands trigger a state dump.
- **The Rust solver takes ~0.4s per solve.** With up to 6 re-solves per turn (worst case), that's ~2.4s — still fast enough.
- **Don't break the existing `solve` recording format.** Add `predicted_post_move` alongside existing `predicted_states`, don't replace.
- **The failure_db is the tuner's training corpus.** Every desync record should include: which sub-action (move vs attack), the predicted state, the actual state, and the diff. This is the data the auto-tuner uses to improve weights.
- **`verify_action` currently classifies desyncs** into categories (click_miss, death, damage_amount, push_dir, etc.). Keep this classification but extend it for move-specific desyncs (mech_position_wrong, move_blocked, etc.).
- **Bridge commands are fire-and-forget** — `writer.py` writes to `/tmp/itb_cmd.txt`, the Lua side picks it up. There's no response channel. State verification happens by reading `/tmp/itb_state.json` AFTER the command executes. Add appropriate waits for the game to process each command.

## Success Criteria

1. `auto_turn` executes 6 sub-steps per turn (move, attack × 3 mechs), reading actual board state after each
2. Any desync between predicted and actual state triggers immediate re-solve
3. Re-solve uses the ACTUAL board state (not the stale predicted one)
4. The Rust solver supports partial-turn input (DONE / MID_ACTION / ACTIVE mech states)
5. failure_db records per-sub-action desyncs with full predicted/actual diffs
6. Manual play (`click_action`) also supports the split move/attack verification
7. All existing tests pass
8. CLAUDE.md reflects the new architecture

## File Structure Reference

See CLAUDE.md "File Structure" section for the full tree. Key paths:
- `game_loop.py` — CLI entry point
- `src/loop/commands.py` — all command implementations
- `src/bridge/` — bridge protocol (reader.py, writer.py, protocol.py, modloader.lua)
- `src/model/board.py` — Board dataclass
- `src/solver/` — Python solver (fallback)
- `rust_solver/src/` — Rust solver (primary, ~60 tests)
- `weights/active.json` — current solver weights
- `recordings/failure_db.jsonl` — desync training data
- `sessions/active_session.json` — session state
