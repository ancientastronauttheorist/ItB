# Into the Breach Achievement Bot

## Project Goal

Earn all 70 achievements in Into the Breach autonomously. The game runs natively on macOS. State is extracted via a Lua bridge (file-based IPC through `/tmp/`). Game actions go through the bridge for combat, and through MCP mouse clicks for UI (deployment, menus, shop, rewards, island nav). The user watches in real-time.

## Important Context

- Turn-based, 8×8 grid, deterministic, perfect information — every enemy telegraphs its attack.
- ITB-ModLoader (Lua) works on Mac via `modloader.lua`. Bridge writes `/tmp/itb_state.json`, reads `/tmp/itb_cmd.txt`.
- Steam App ID: 590380.
- `scripts/install_modloader.sh` copies the bridge Lua into the Steam app bundle — run after editing `src/bridge/modloader.lua`, then restart the game.

## Architecture

**Five layers:**

- **Layer 0 — Game loop:** `game_loop.py` CLI + `src/loop/` (session, logger, commands). Claude is the control loop; Python commands are stateless.
- **Layer 1 — State extraction:** `src/bridge/` (primary) and `src/capture/save_parser.py` (fallback). The bridge delivers richer data: targeted tiles, per-enemy attack data, environment hazards with kill flag, deployment zones, objective buildings, attack order.
- **Layer 2 — Game state:** `src/model/` (Board, Unit, WeaponDef). Single source of truth for solver.
- **Layer 3 — Solver:** `rust_solver/` (primary, pyo3 extension `itb_solver`) + `src/solver/simulate.py` (Python parity). Search is constraint-based threat response + bounded search. `EvalWeights` tune scoring without changing search logic.
- **Layer 4 — Strategist:** `src/strategy/` picks `EvalWeights` per achievement target; manages squad/island/shop choices.

**Rebuild the solver** after editing any `rust_solver/src/*.rs`:
```bash
cd rust_solver && maturin build --release && \
  pip3 install --user --force-reinstall target/wheels/itb_solver-0.1.0-cp39-cp39-macosx_11_0_arm64.whl
```

## Execution Model

**Default combat mode: `auto_turn`.** A single `game_loop.py auto_turn` call reads board, solves, executes every mech action via bridge (move → verify → attack → verify, re-solving on desync), and emits an End Turn click plan. It *polls the bridge internally* for the enemy→player transition (up to 45s by default) at entry, waiting for both `phase == combat_player` **and** `active_mechs > 0` — the animation window after End Turn flips phase early but leaves mechs inactive, so checking phase alone falsely proceeds into "No active mechs" errors.

**Typical turn = 2 LLM rounds:** `auto_turn` → click End Turn → `auto_turn` (blocks in Python until next player turn) → click End Turn → ...

**Fallback manual play** (`click_action <i>` / `verify_action <i>` / `click_end_turn`) exists for when the bridge is unavailable — don't use it otherwise.

**Coordinate mapping:**
- Bridge `(x, y)` → visual: `Row = 8 - x`, `Col = chr(72 - y)`. Example: bridge `(3, 5)` = `C5`. Always use A1–H8 visual notation in communication.
- MCP pixel coords: `grid_to_mcp(x, y)` (in `src/control/executor.py`) or `python3 tile_hover.py <TILE>`. Both auto-detect window position via Quartz.
- Island-select click coords: `python3 island_select.py`.
- **End Turn button: `python3 game_loop.py click_end_turn`** — emits a scaled click at window-relative offset `(95, 78)` (see `_UI_END_TURN` in `src/control/executor.py`). The exact MCP coord depends on current window position — don't hardcode it. No hover-verify needed; `_ui_pos()` handles scaling.

## Core Game Rules (Solver-Critical)

The solver enforces these; use them when reviewing solver output or writing tests.

**Terrain kills:** Water and Chasm kill non-flying ground units. Lava kills like water but sets flying units on Fire. Pushing enemies into these is a primary kill method.

**Push:** 1 tile in a direction. If blocked by unit/mountain/edge, the pushed unit takes 1 bump damage instead. If blocked by a building, *both* pushed unit and building take 1 bump. Chain pushing (A pushed into B) doesn't move B — both take bump. Push/bump damage ignores Armor and ACID.

**Damage types:**
- Weapon damage: −1 from Armor, ×2 from ACID
- Push / bump / fire / blocking damage: ignores Armor and ACID
- Blocking damage fires when a Vek tries to emerge on an occupied tile

**Status effects:**
- **Fire:** 1 dmg/turn start. Removed by repair, water, or freezing.
- **Frozen:** invincible + immobilized. Any damage unfreezes (0 dmg dealt).
- **ACID:** doubles weapon damage. Persists until unit dies.
- **Smoke:** prevents attack AND repair. Cancels Vek attacks when on smoke tile at execution.
- **Shield:** blocks one instance of damage + negative effects. Removed by direct damage.
- **Armor:** −1 weapon damage (floor 0). No effect on push/fire/bump.
- **Webbed:** can't move, can still attack. Breaks when pushed.

**Terrain HP:**
- **Mountain:** 2 HP (2=full, 1=damaged, 0=rubble/walkable). Any weapon damage reduces by 1.
- **Building:** 1 HP (objective buildings 2). Any damage destroys all on the tile. Reduces grid power by old HP.
- **Ice:** intact → cracked → water (non-flying drowns).

**Repair:** any mech can repair instead of attacking. +1 HP, clears Fire and ACID. Can't repair on smoke.

Extended rules: `data/ref_game_mechanics.md`.

## Operational Rules

1. Always verify state after each mech action (the bridge does this in `auto_turn` automatically). Save file only updates at turn boundaries; bridge updates per sub-action.
2. Never execute mech N+1 before the verify for mech N returns PASS, unless you consciously decide to log+continue past a desync.
3. Click tile centers, not sprites — sprites render 100–170 px above tile center. `click_action` / `grid_to_mcp` already do this.
4. After every failed run, analyze the critical turn. Save a snapshot first.
5. To select a mech in manual play, click its tile on the board. No portraits, no Tab, no keyboard.
6. Priority order: buildings > threats > kills > spawns.
7. **Default combat:** `python3 game_loop.py auto_turn --time-limit 10` each turn. It polls for player phase at entry, solves, executes all mech actions via bridge, emits an End Turn click plan. Dispatch that plan (or run `click_end_turn` — both scale the End Turn coord to the current window, never hardcode it) and loop. Manual-play fallback (`click_action`/`verify_action`/`click_end_turn`) is only for when the bridge is unavailable. Bridge sub-action commands (`move_mech`, `attack_mech`, `skip_mech`, `repair_mech`) are used internally by `auto_turn` — never call directly.
8. Never move onto ACID tiles voluntarily — doubles damage, disables armor.
9. **Self-improvement:** every process error triggers an immediate CLAUDE.md update with a guard or fix. Every mistake makes the process permanently better.
10. Bridge-to-visual coordinate rule (see Execution Model). Use A1–H8 in all communication.
11. **No keyboard during combat.** End Turn is the only MCP click needed per turn — dispatch the scaled coord from `click_end_turn` (or `auto_turn`'s emitted plan). The raw offset is `(95, 78)` window-relative; never paste a fixed MCP pair since the window can move.
12. Use all mech actions every turn — even suboptimal moves beat skipping.
13. The solver handles environment hazards via `environment_danger_v2`: each entry is `[x, y, damage, kill_int]`. `kill_int=1` = lethal (Air Strike, Lightning, Cataclysm→chasm, Seismic→chasm, Tidal→water; bypasses shield/frozen/armor/ACID). `kill_int=0` = non-lethal (Wind/Sand/Snow). Env ticks fire BEFORE Vek attacks in enemy phase.
14. On crash/timeout recovery, always start with `cmd_read` + `cmd_solve`. Never resume a previous solution — the board may have changed.
15. Save file updates only at turn boundaries. Bridge does not have this limit — `verify_action` reads fresh bridge state.
16. **Deployment:** `game_loop.py read` prints deploy tiles with visual notation AND MCP pixel coords. Click those coords directly; the game prompts mechs sequentially. `tile_hover.py <TILE>` for single-tile lookup.
17. **Hover-verify-click — for novel UI only.** Before `left_click`-ing an unfamiliar UI element (shop items, reward cards, new menus), do: `mouse_move` → `screenshot` → `left_click`. **Exempt:** the End Turn button (use `click_end_turn`'s emitted scaled coord; calibrated offset `(95, 78)` relative to the window) and any combat tile click computed by `grid_to_mcp()` (calibrated <2px — `click_action` handles internally).
18. **Prefer `game_loop.py read` over screenshots for combat state.** Screenshots are 100–200 kB each and accumulate fast. Reserve screenshots for novel UI screens (defeat, rewards, shop, CEO cutscenes) and for verifying unexpected state.
19. **Always follow the solver — never override.** The solver encodes push directions, bump damage, projectile re-aiming, terrain interactions, env_danger ordering — your manual analysis will be wrong or incomplete. Execute what `game_loop.py solve` outputs. When `verify_action` reports a desync, the failure_db record is the useful signal (it feeds the auto-tuner). Overriding the solver suppresses that data. Only exception: solver returns empty (timeout) — play manually via screenshot reasoning. Rationale: `feedback_trust_solver.md`.
20. **Research gate — never solve past an unknown.** When `game_loop.py read` flags `requires_research: true`, or when `solve` / `auto_turn` return `error: RESEARCH_REQUIRED`, the self-healing loop has detected a pawn type, terrain, weapon, or screen we've never catalogued. Solving past it produces confidently-wrong plays. Do this before resuming combat: (a) `game_loop.py snapshot research_gate_<turn>` for rollback, (b) `game_loop.py research_next` to get the MCP capture plan, (c) dispatch `plan.batch` via `mcp__computer-use__computer_batch`, zoom each `plan.crops[i].region`, run Vision with each bundled `prompts[crop_name]` to produce JSON per crop, (d) `game_loop.py research_submit <research_id> '<json>'`. If the submit result includes `community_queries.queries`, (e) `WebFetch` each URL (Steam discussions + r/IntoTheBreach), summarize each into `{url, excerpt, confidence}` and (f) `game_loop.py research_attach_community <research_id> '<notes_json>'` to persist the corroborating community notes. Repeat until `research_next` returns `status: NO_WORK`. Only then `auto_turn`. Rationale: `docs/self_healing_loop_design.md` §Missing wire.
21. **Grid-drop investigation gate — fire now, not later.** When `auto_turn` returns `status: "INVESTIGATE"`, the solver's prediction lost grid power in a way the sim didn't model. This is exactly how Prime_ShieldBash and Ramming Engines' empty-charge self-damage bugs surfaced — we missed the signal for multiple runs. Never click `pending_end_turn_batch` before resolving. For each entry in `investigations`: (a) read the `snapshot_path` (has `predicted.json`, `actual_board.json`, `context.json` with `grid_power_diff` + `building_hp_diffs` + `failure_db_id`), (b) spawn an Explore agent with those three files and the prompt "trace this unpredicted grid loss to a weapon-def, simulator, or push-chain bug — propose a fix with file+line and confidence level", (c) if the agent returns a concrete fix with high confidence, apply it, rebuild Rust if `rust_solver/src/*.rs` changed, run `bash scripts/regression.sh` to verify nothing else regressed, (d) if fix applied, `replay <run_id> <turn>` on the new solver to confirm it now predicts the actual grid power. Only then dispatch `pending_end_turn_batch` via `computer_batch`. If the agent cannot propose a fix (low confidence / needs more data), log that in the decision log, dispatch the batch, and continue — not every mystery is fixable mid-turn.

## Phase Protocols

Each phase: read → act → verify. Detailed command semantics are in **Game Loop Command Reference** below.

- **ISLAND_SELECT** (start of run): `python3 island_select.py` picks one of 4 corporations. Click its coord. Click through CEO intro. → ISLAND_MAP.
- **ISLAND_MAP:** `game_loop.py read` → pick mission (prefer bonus objectives for the achievement target) → click mission on map → mission briefing → click preview or start button → DEPLOYMENT.
- **DEPLOYMENT:** `game_loop.py read` prints valid deploy tiles with MCP coords. Click 3 in sequence (FORWARD, MID, SUPPORT recommendation). Click CONFIRM. → COMBAT_PLAYER_TURN.
- **COMBAT_PLAYER_TURN:** `auto_turn --time-limit 10` → dispatch End Turn click at `(295, 215)` → loop. The next `auto_turn` blocks in Python until the next player turn or mission end. On game_over or empty solution, falls back to screenshot-based reasoning.
- **MISSION_END:** screenshot reward screen → click reward → `snapshot <label>` → ISLAND_MAP (or ISLAND_COMPLETE if all missions done).
- **SHOP:** appears *only after winning a whole island* (4 missions + finale), not mid-island. Do NOT expect a shop between missions — grid repair opportunities come from time-pod rewards and island completions, full stop. Screenshot when it appears (neither save nor bridge distinguish shop from map). Buy grid repairs first, then weapons/cores per strategy. → ISLAND_MAP (next island) or RUN_END.
- **RUN_END:** `snapshot run_end`. If defeat, analyze critical turns from decision log. Check achievement progress. Start new run with next target.

### Error recovery

- **Unexpected screen:** screenshot, log to decision log, diagnose visually.
- **State not updating:** `refresh_bridge_state`. If bridge dead, retry save-file verify up to 5× with 1.5s delay.
- **Grid power = 0:** log, snapshot, analyze.
- **Crash/timeout:** fresh `cmd_read` + `cmd_solve`. Never resume an old solution.

## Game Loop Command Reference

All commands are `game_loop.py <name> [args]`. Each is stateless: read state, compute, output, exit. Session state persists in `sessions/active_session.json`.

**State reading:**
- `read` — Bridge state (primary) or save file (fallback). Prints phase, board, threats, active mechs, deployment zone with MCP coords, env hazards. Auto-records to `recordings/<run_id>/`.
- `status` — Quick summary: turn, grid, mech HP, threats, objectives.
- `verify_action <index>` — Per-action diff: refreshes bridge, diffs actual vs the predicted snapshot captured during `replay_solution`, classifies (click_miss / death / damage_amount / push_dir / grid_power / status / terrain / tile_status / spawn / pod), writes desync to `recordings/<run_id>/failure_db.jsonl`. Never re-solves.
- `verify [index]` — Legacy save-parser-based path (retries 5×, 1.5s each). Superseded by `verify_action` in bridge mode.

**Solving & recording:**
- `solve` — Runs the solver, stores solution in session, prints action sequence. Recording includes structured actions, per-action `ActionResult`, per-action `predicted_states` (input to `verify_action`), predicted post-enemy board, score breakdown, search stats.
- Recordings from `read`/`solve` land in `recordings/<run_id>/m<NN>_turn_<NN>_<label>.json`. Dedup guard prevents duplicate `(mission, turn)` pairs.

**Combat execution:**
- `auto_turn [--time-limit N] [--no-wait] [--max-wait S]` — Full turn via bridge with per-sub-action verification. Polls at entry for `combat_player` phase **and** `active_mechs > 0` (up to `--max-wait` seconds, default 45; disable with `--no-wait`). Returns an MCP click plan for End Turn. On desync, re-solves from actual board with partial mech states (DONE = inactive, MID_ACTION = can_move=false, ACTIVE = full search).
- `click_action <i>` — Pure planner for manual play. Emits a `computer_batch`-ready sequence for ONE mech action (select-tile, optional move, weapon icon, target). Handles dash weapons (skip move click), Repair (click Repair button), passives (no-op).
- `click_end_turn` — Pure planner. Emits a single click on End Turn.
- `click_balanced_roll` — Pure planner. Emits a single click on the Balanced Roll button on the squad-select screen. Dispatch before clicking Start so a Balanced Roll (unique mech classes, ≤4 weapons total) is seeded instead of the default squad.
- `execute <index>` / `end_turn` — Bridge-mode action commands. Used internally by `auto_turn`. In manual play, use `click_action` / `click_end_turn` instead.

**Full-mission automation:**
- `auto_mission [--max-turns N]` — Full mission: auto-deploy → combat loop → mission end. Final turn is force-flushed to failure_db on exit. Falls back to Claude for reward/shop/map screens.

**Analysis & tuning:**
- `replay <run_id> <turn> [--time-limit N]` — Reconstruct Board from a recorded JSON and re-run the solver. Compares new solution with original.
- `analyze [--min-samples N]` — Read failure_db.jsonl, report patterns by trigger / severity / squad / island.
- `validate <old.json> <new.json> [--failures-only] [--time-limit N]` — Compare two weight versions across recorded boards.
- `tune [--iterations N] [--min-boards N] [--time-limit N]` — Auto-tune EvalWeights. Hybrid objective: `mean_fixed_score − 100 * fired_failure_count`.

**Run management:**
- `new_run <squad> [--achieve X Y] [--difficulty N] [--tags audit ...]` — Initialize new session. Use `--tags audit` for environment-audit playthroughs (those failures stay out of the tuner corpus).
- `snapshot <label>` — Save current state for regression.
- `log <message>` — Append reasoning to the decision log.

## Achievement Context

Progress persists in session. 9/70 earned, 61 remaining across 4 difficulty tiers (Green >40%, Yellow 20–40%, Orange 10–20%, Red <10%).

- Squad-specific achievements need the matching squad — check `data/ref_achievement_strategies.md`.
- Cumulative achievements (reputation, civilians, pilot reuse) accrue across runs.
- Achievement strategies bias solver scoring via `EvalWeights` in `src/solver/evaluate.py`.
- Full checklist: `TODO.md`. Detailed metadata: `data/achievements_detailed.json`.

## Reference Material

Codebase layout, knowledge base tables, and data file inventory live in `docs/reference.md` — read that when you need to find where something is.
