# Into the Breach Achievement Bot Agent Guide

This file is adapted from `CLAUDE.md` so Codex and other agent runners can pick up the same project instructions.

## Project Goal

Earn all 70 achievements in Into the Breach autonomously. The game runs natively on macOS. State is extracted via a Lua bridge (file-based IPC through `/tmp/`). Game actions go through the bridge for combat, and through MCP mouse clicks for UI (deployment, menus, shop, rewards, island nav). The user watches in real-time.

## Important Context

- Turn-based, 8×8 grid, deterministic, perfect information — every enemy telegraphs its attack.
- ITB-ModLoader (Lua) works on Mac via `modloader.lua`. Bridge writes `/tmp/itb_state.json`, reads `/tmp/itb_cmd.txt`.
- Steam App ID: 590380.
- `scripts/install_modloader.sh` copies the bridge Lua into the Steam app bundle — run after editing `src/bridge/modloader.lua`, then restart the game.

## Architecture

**Five layers:**

- **Layer 0 — Game loop:** `game_loop.py` CLI + `src/loop/` (session, logger, commands). The agent is the control loop; Python commands are stateless.
- **Layer 1 — State extraction:** `src/bridge/` (primary) and `src/capture/save_parser.py` (fallback). The bridge delivers richer data: targeted tiles, per-enemy attack data, environment hazards with kill flag, deployment zones, objective buildings, attack order.
- **Layer 2 — Game state:** `src/model/` (Board, Unit, WeaponDef). Single source of truth for solver.
- **Layer 3 — Solver:** `rust_solver/` (the only solver AND the only simulator, pyo3 extension `itb_solver` with entry points `solve` / `solve_top_k` / `solve_beam` / `score_plan` / `project_plan` / `replay_solution`). Search is constraint-based threat response + bounded search. `EvalWeights` tune scoring without changing search logic. On the Python side: `src/solver/solver.py` is now a 121-line wrapper holding `MechAction` / `Solution` dataclasses and `replay_solution()` (a thin shim around `itb_solver.replay_solution` that adds Python's `evaluate_breakdown` for audit-only `score_breakdown`). `src/solver/evaluate.py` owns weight/threat/psion machinery for that breakdown — never touched by `solve()`. **`src/solver/simulate.py` is gone** (deleted in the simulate.py-removal PR series); every diagnose-loop fix targets `rust_solver/src/*.rs`, validator + agent prompt enforce `target_language=rust`.
- **Layer 4 — Strategist:** `src/strategy/` picks `EvalWeights` per achievement target; manages squad/island/shop choices.

**Rebuild the solver** after editing any `rust_solver/src/*.rs`:
```bash
cd rust_solver && maturin build --release && \
  pip3 install --user --force-reinstall target/wheels/itb_solver-0.1.0-cp39-cp39-macosx_11_0_arm64.whl
```
If `maturin` is not on `PATH`, use `python3 -m maturin build --release`
from `rust_solver/` with the same `pip3 install` command.

If `cargo test` hits a rustc incremental-compilation ICE, rerun with
`CARGO_INCREMENTAL=0` before treating it as a code/test failure. The regression
script already sets this guard.

## Execution Model

**Default combat mode: `auto_turn`.** A single `game_loop.py auto_turn` call reads board, solves, executes every mech action via bridge (move → verify → attack → verify, re-solving on desync), and emits an End Turn click plan. It *polls the bridge internally* for the enemy→player transition (up to 45s by default) at entry, waiting for both `phase == combat_player` **and** `active_mechs > 0` — the animation window after End Turn flips phase early but leaves mechs inactive, so checking phase alone falsely proceeds into "No active mechs" errors.

**Typical turn = 2 agent rounds:** `auto_turn` → click End Turn → `auto_turn` (blocks in Python until next player turn) → click End Turn → ...

**Fallback manual play** (`click_action <i>` / `verify_action <i>` / `click_end_turn`) exists for when the bridge is unavailable — don't use it otherwise.

**Coordinate mapping:**
- Bridge `(x, y)` → visual: `Row = 8 - x`, `Col = chr(72 - y)`. Example: bridge `(3, 5)` = `C5`. Always use A1–H8 visual notation in communication.
- MCP pixel coords: `grid_to_mcp(x, y)` (in `src/control/executor.py`) or `python3 tile_hover.py <TILE>`. Both auto-detect window position via Quartz.
- Island-select click coords: `python3 island_select.py`.
- **End Turn button: `python3 game_loop.py click_end_turn`** — emits both legacy screen/global coords and `codex_computer_use_batch` window-local coords for Codex Computer Use. In Codex Computer Use, dispatch `codex_computer_use_batch` (or the per-click `window_x`/`window_y`), not the legacy `x`/`y`. The calibrated End Turn offset is `(126, 120)` window-relative.

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
- **Webbed:** can't move, can still attack. Breaks only when the unit actually changes tiles, or when the webber moves/dies. A blocked push/bump leaves the unit webbed.

**Terrain HP:**
- **Mountain:** 2 HP (2=full, 1=damaged, 0=rubble/walkable). Any weapon damage reduces by 1.
- **Building:** 1 HP (objective buildings 2). Any damage destroys all on the tile. Reduces grid power by old HP.
- **Ice:** intact → cracked → water (non-flying drowns).

**Repair platforms:** Mission_Repair places `Item_Repair_Mine` tiles. Any live
unit that lands on one triggers the item, heals by the engine's `SpaceDamage(-10)`
(live captures show 3-max-HP mechs can become `5/3`; 2-max-HP mechs cap at
`4/2`, so model this as `max_hp + 2`, not a flat 5 HP), consumes the platform,
and increments `repair_platforms_used` toward the 3-platform objective. Raw
progress can exceed the objective target (for example `4/3`); clamp only in UI
scoring/presentation. It is not the mech Repair action; do not assume it clears
Fire/ACID/Frozen unless a capture proves the engine does so.

**Repair:** any mech can repair instead of attacking. +1 HP, clears Fire and ACID. Can't repair on smoke.

Extended rules: `data/ref_game_mechanics.md`.

## Operational Rules

1. Always verify state after each mech action (the bridge does this in `auto_turn` automatically). Save file only updates at turn boundaries; bridge updates per sub-action.
2. Never execute mech N+1 before the verify for mech N returns PASS, unless you consciously decide to log+continue past a desync.
3. Click tile centers, not sprites — sprites render 100–170 px above tile center. `click_action` / `grid_to_mcp` already do this.
4. After every failed run, analyze the critical turn. Save a snapshot first.
5. To select a mech in manual play, click its tile on the board. No portraits, no Tab, no keyboard.
6. Priority order: buildings > threats > kills > spawns.
7. **Default combat:** `python3 game_loop.py auto_turn --time-limit 10` each turn. It polls for player phase at entry, solves, executes all mech actions via bridge, emits an End Turn click plan. In Codex Computer Use, dispatch `codex_computer_use_batch` (window-local); in legacy batch tools, dispatch `batch` (screen/global). Manual-play fallback (`click_action`/`verify_action`/`click_end_turn`) is only for when the bridge is unavailable. Bridge sub-action commands (`move_mech`, `attack_mech`, `skip_mech`, `repair_mech`) are used internally by `auto_turn` — never call directly.
8. Never move onto ACID tiles voluntarily — doubles damage, disables armor.
9. **Self-improvement:** every process error triggers an immediate AGENTS.md update with a guard or fix. Every mistake makes the process permanently better.
10. Bridge-to-visual coordinate rule (see Execution Model). Use A1–H8 in all communication.
11. **No keyboard during combat.** End Turn is the only MCP click needed per turn. `click_end_turn` / `auto_turn` emit legacy `batch` coords in screen/global space plus `codex_computer_use_batch` coords in Codex window-local space. After `get_app_state`, use `codex_computer_use_batch` or the visible End Turn button center, then verify the screen switches to ENEMY ACTIVITY / ENEMY TURN.
12. Use all mech actions every turn — even suboptimal moves beat skipping.
13. The solver handles environment hazards via `environment_danger_v2`: each entry is `[x, y, damage, kill_int]`. `kill_int=1` = lethal (Air Strike, Lightning, Cataclysm→chasm, Seismic→chasm, Tidal→water; bypasses shield/frozen/armor/ACID). `kill_int=0` = non-lethal (Wind/Sand/Snow). Env ticks fire BEFORE Vek attacks in enemy phase.
14. On crash/timeout recovery, always start with `cmd_read` + `cmd_solve`. Never resume a previous solution — the board may have changed.
15. Save file updates only at turn boundaries. Bridge does not have this limit — `verify_action` reads fresh bridge state.
16. **Deployment:** prefer `python3 game_loop.py deploy_recommended`, which sends bridge `DEPLOY uid x y` commands for the ranked FORWARD/MID/SUPPORT tiles and verifies the placed mech coords. Click the visible CONFIRM button afterward. If the bridge helper is unavailable, fall back to `game_loop.py read` MCP coords and click the 3 recommended tiles manually, then CONFIRM.
17. **Hover-verify-click — for novel UI only.** Before `left_click`-ing an unfamiliar UI element (shop items, reward cards, new menus), do: `mouse_move` → `screenshot` → `left_click`. **Exempt:** the End Turn button (use `codex_computer_use_batch` in Codex Computer Use; calibrated offset `(126, 120)` relative to the window) and any combat tile click computed by `grid_to_mcp()` (calibrated <2px — `click_action` handles internally).
18. **Prefer `game_loop.py read` over screenshots for combat state.** Screenshots are 100–200 kB each and accumulate fast. Reserve screenshots for novel UI screens (defeat, rewards, shop, CEO cutscenes) and for verifying unexpected state.
19. **Always follow the solver — never override.** The solver encodes push directions, bump damage, projectile re-aiming, terrain interactions, env_danger ordering — your manual analysis will be wrong or incomplete. Execute what `game_loop.py solve` outputs. When `verify_action` reports a desync, the failure_db record is the useful signal (it feeds the auto-tuner). Overriding the solver suppresses that data. Only exception: solver returns empty (timeout) — play manually via screenshot reasoning. Rationale: `feedback_trust_solver.md`.
20. **Research gate — never solve past an unknown.** When `game_loop.py read` flags `requires_research: true`, or when `solve` / `auto_turn` return `error: RESEARCH_REQUIRED`, the self-healing loop has detected a pawn type, terrain, weapon, or screen we've never catalogued. Solving past it produces confidently-wrong plays. Do this before resuming combat: (a) `game_loop.py snapshot research_gate_<turn>` for rollback, (b) `game_loop.py research_next` to get the MCP capture plan, (c) dispatch `plan.batch` via `mcp__computer-use__computer_batch`, zoom each `plan.crops[i].region`, run Vision with each bundled `prompts[crop_name]` to produce JSON per crop, (d) `game_loop.py research_submit <research_id> '<json>'`. If the submit result includes `community_queries.queries`, (e) `WebFetch` each URL (Steam discussions + r/IntoTheBreach), summarize each into `{url, excerpt, confidence}` and (f) `game_loop.py research_attach_community <research_id> '<notes_json>'` to persist the corroborating community notes. After a display-name submit (e.g. "Centipede") for a tiered bridge type (e.g. `Centipede1`), ensure the exact bridge type(s) are present in `data/known_types.json`; otherwise `research_next` can say `NO_WORK` while `auto_turn` still gates on the tiered type. Repeat until `research_next` returns `status: NO_WORK`. Only then `auto_turn`. Rationale: `docs/self_healing_loop_design.md` §Missing wire.
21. **Codex Computer Use coordinate caveat.** `research_next` and legacy `grid_to_mcp` plans emit MCP/global coordinates for the old batch tool. The Codex Desktop `mcp__computer_use__.click` tool expects screenshot/window-local coordinates, so don't paste those MCP coords directly into it — use the emitted `codex_computer_use_batch` when present, the visible tile center from the screenshot, or a helper that explicitly says its coords are Codex window-local. This came from a 2026-05-04 research miss where an MCP coord intended for `Snowtank1` selected the wrong visible unit.
22. **Simulator version discipline.** `SIMULATOR_VERSION` in `src/solver/verify.py` pins the semantic behavior of the Rust + Python simulators. Bump it whenever a simulator change alters predictions on a given board (e.g., Storm Generator implemented, Psion regen applied, Spartan Shield fixed, PushDir::Flip semantics changed). Weight-tuning changes do NOT bump it. Every new solve recording and failure_db entry is stamped with the current version. Before bumping: `cp recordings/failure_db.jsonl recordings/failure_db_snapshot_sim_v<old>.jsonl` to archive the pre-bump corpus. `cmd_tune` refuses to run on a mixed-version corpus unless `--accept-version-change` is passed.
23. **Grid-drop investigation gate — fire now, not later.** When `auto_turn` returns `status: "INVESTIGATE"`, the solver's prediction lost grid power in a way the sim didn't model. This is exactly how Prime_ShieldBash and Ramming Engines' empty-charge self-damage bugs surfaced — we missed the signal for multiple runs. Never click `pending_end_turn_batch` before resolving. For each entry in `investigations`: (a) read the `snapshot_path` (has `predicted.json`, `actual_board.json`, `context.json` with `grid_power_diff` + `building_hp_diffs` + `failure_db_id`), (b) spawn an Explore agent with those three files and the prompt "trace this unpredicted grid loss to a weapon-def, simulator, or push-chain bug — propose a fix with file+line and confidence level", (c) if the agent returns a concrete fix with high confidence, apply it, rebuild Rust if `rust_solver/src/*.rs` changed, run `bash scripts/regression.sh` to verify nothing else regressed, (d) if fix applied, `replay <run_id> <turn>` on the new solver to confirm it now predicts the actual grid power. Only then dispatch `pending_end_turn_batch` via `computer_batch`. If the agent cannot propose a fix (low confidence / needs more data), log that in the decision log, dispatch the batch, and continue — not every mystery is fixable mid-turn.

24. **Diagnosis loop — "drain the queue", "run the loop", "diagnose this run" all mean the same protocol.** When `verify_action --diagnose` is on (or env `ITB_AUTO_DIAGNOSE=1`), desyncs accrue in `session.diagnosis_queue`. The harness — that's you — drains the queue **between turns**, NEVER inside `auto_turn` (45s enemy-animation budget; design doc §13 #17). Per-call protocol:

    a. **Drain one entry.** `python3 game_loop.py diagnose_next` pops one pending failure, runs Layer 2 (rejections → known_gaps → rules.yaml). Outputs `rule_match` / `needs_agent` / `insufficient_data` / `rejected` / `EMPTY`. On `EMPTY`, stop and tell the user — don't spin polling.
    b. **`needs_agent` → dispatch.** Read the `## Agent prompt` block from `recordings/<run_id>/diagnoses/<failure_id>.md`, dispatch via the available agent/delegation tool with an exploration-oriented subagent. The validator tolerates prose-wrapped + multi-`{...}` agent output (last block wins, braces inside string literals are skipped) but enforces `target_language=rust`, every `suspect_files[*].path` resolves, every cited line exists, `confidence ∈ {high,medium,low}`, `fix_snippet.before` and `.after` both non-empty. Pipe the JSON via `python3 game_loop.py diagnose_apply_agent <id> <json|path>`. On validator failure: read the error list, fix the JSON OR `reject_diagnosis` if the proposal is bad on its merits.
    c. **`rule_match` → leave alone.** Rule fixes are conceptual prose (e.g. "guard set_active(false) on weapon_id != WId::None"), not Edit-applicable. Surface the rule_id + suspect_files to the user; `apply_diagnosis` will refuse a rule_match anyway.
    d. **`agent_proposed` → ASK before applying.** Do NOT auto-fire `apply_diagnosis`. It mutates source files, atomically bumps SIMULATOR_VERSION in BOTH `rust_solver/src/lib.rs` and `src/solver/verify.py`, archives `failure_db.jsonl`, runs `bash scripts/regression.sh`, and reverts on failure. Always `apply_diagnosis <id> --dry-run` first to surface the plan, then ask the user before the real apply. Multi-location fixes (function signature changes that need both def + call sites edited) currently can't be expressed in one `fix_snippet` — design doc §15.1 known limitation; reject those with a reason citing it.
    e. **`apply_diagnosis` refused on dirty workdir → surface, don't auto-resolve.** Refusal is by design (don't clobber user work). Print the dirty paths to the user; do NOT `git stash` or `git commit` on their behalf to "make it apply". Per AGENTS.md "Executing actions with care".
    f. **`apply_diagnosis` succeeded → don't auto-commit.** The memory rule about auto-pushing routine commits doesn't apply to auto-applied sim changes — those need eyeballs. Show `git diff`, ask the user to commit. The commit message should include the failure_id and the agent's confidence.
    g. **`reject_diagnosis <id> --reason "..."` is the feedback channel.** Use it whenever a proposal is wrong (incomplete fix, wrong direction, would not compile, regresses corpus). The (diff_signature × sim_version × proposed_fix_sig) gets recorded in `diagnoses/rejections.jsonl` so the same wrong proposal can't recur. `--force` on diagnose bypasses, for when a rejection turns out to have been premature.
    h. **One drain per call** unless the user says "drain all" / "clear the queue" — agent dispatches cost real tokens. Report queue depth and ask before continuing. Exception: if every pending entry resolves to `rule_match` or `insufficient_data` (no agent dispatch), drain them all in one pass — they're cheap.

    Full spec: `docs/diagnosis_loop_design.md`. Live-run hardening retrospective: §15.1.

25. **New-run setup is achievement-aware: Easy difficulty + Advanced Edition ON + the target squad.** Updated 2026-05-06 from the temporary Balanced Roll default. Balanced Roll remains correct for `--mode solver_eval` and random-squad achievements, but normal achievement hunting should first run `python3 game_loop.py achievements --sync` when `.env` has `STEAM_API_KEY` and `STEAM_ID`, then pick an actual unfinished squad via `python3 game_loop.py recommend_squad --tags achievement` / `python3 game_loop.py new_run auto --tags achievement`. On every new game's setup screen: click **Easy**, ensure **Advanced Edition** toggle is ON, select the recommended squad card (or click **Balanced Roll** only when the setup says so), then **Start**. When invoking `python3 game_loop.py new_run`, omit `--difficulty` (default 0 = Easy) or pass `--difficulty 0`. Don't fall back to Normal/Hard, including after defeats, unless the run is explicitly tagged as solver evaluation. Rationale: `feedback_playstyle.md` plus squad-locked achievement targeting.
26. **Session lock discipline:** never run `game_loop.py read`, `status`, `solve`, `deploy_recommended`, `auto_turn`, `diagnose_next`, `research_next`, `research_submit`, `research_resolve`, or other session-mutating game-loop commands in parallel. They share `sessions/active_session.json.lock`; run them one at a time, then parallelize only independent file reads or analysis commands.
27. **No repo-wide Rust formatting during tactical fixes.** This Rust tree is not globally `cargo fmt`-clean; running `cargo fmt` rewrites many unrelated files and hides the simulator change under formatting noise. For live/debug fixes, keep Rust edits hand-scoped to touched hunks. Only run a repo-wide formatter as its own explicit cleanup task.
28. **Do not chain session-mutating commands.** Even with `&&`, commands like `py_compile && game_loop.py read` make live logs harder to audit and can hide which step changed session state. Run formatting/compile checks and game-loop commands as separate terminal calls.
29. **Final-island save phase anomaly.** During `Mission_Final` and `Mission_Final_Cave`, `saveData.lua` can report `mission_ending` while the Lua bridge and visible screen are still in live combat. If `cmd_read` / `auto_turn` says `mission_ending` but the screen shows active final combat, trust the fresh bridge when `mission_id` is `Mission_Final` or `Mission_Final_Cave` and at least one mech is active. Conversely, if `auto_turn` waits out with `active_mechs=0`, it now returns `status="TERMINAL_OR_MISSION_END"` and clears the stale active solution; check the visible screen for Victory / Region Secured / rewards / defeat before issuing more combat commands.
30. **Safety block emergency protocol.** On a safety block, `cmd_solve` now automatically widens to `solve_top_k(..., 100)` and, if the session has temporary soft-disabled weapons, runs a second emergency top-k pass with `disabled_actions` removed from the payload. This does **not** mutate `session.disabled_actions`; it only lets the current candidate search recover a clean plan. If it still returns `SAFETY_BLOCKED`, use manual analysis / `--allow-dirty-plan` only with explicit acceptance. On the final bomb turn, a dirty plan is acceptable when the predicted grid remains above 0, the Renfield Bomb survives, and no clean candidate is found.
31. **Research queue cleanup.** If `research_next` reports stale pending known-type entries, use `python3 game_loop.py research_resolve <TYPE> --kind behavior_novelty --reason "<why>"` rather than hand-editing `sessions/active_session.json`. The command validates `<TYPE>` against `data/known_types.json` and records a `manual_resolved` result with attempts/diff metadata.
32. **Research queue peek still matters.** If `auto_turn` completes but `research_queue_peek` contains a current-board unknown such as `BigBomb`, snapshot and run `research_next` / `research_submit` before advancing another turn, even if no hard `RESEARCH_REQUIRED` gate fired.
33. **Deployment roster supplementation is built in.** `deploy_recommended` merges live bridge mechs, the last active solution, and save-file `GameData.current.mechs` into stable UIDs 0/1/2. If the bridge lists only two unplaced mechs, do not manually deploy the third first — run `deploy_recommended` and let the bridge `DEPLOY uid x y` verification tell us whether a UID is truly missing.
34. **Projectile-grapple attacks are line attacks, not melee.** Burnbug/Gastropod proboscis weapons (`BurnbugAtk1`, `BurnbugAtk2`, `BurnbugAtkB`, `GastropodAtk1`, `GastropodAtk2`) trace from the attacker's current tile along the original queued direction until the first projectile blocker, then damage that blocker and grapple: hit pawns are pulled toward the attacker, objects pull the attacker toward the object. A vacated first target tile does NOT cancel the shot. If an unexpected grid loss follows a moved Burnbug/Gastropod, first check for a building farther down that line. Regression anchor: Normal run `20260504_210332_088`, mission 1 turn 1, F7 `(1,2)` building loss fixed in simulator v44.
35. **Trust engine terrain ids over stale terrain names.** Shipped map files and Lua constants have terrain id `5` = Ice, not Lava. Older bridge builds mislabeled id 5 as `"lava"`, causing false terrain-death predictions on Pinnacle ice and the Coal Plant loss chain in Normal run `20260504_210332_088`, mission 1 turn 2. Parser code must prefer `terrain_id` normalization when present; bridge Lua must derive `TERRAIN_NAMES` from engine globals (`TERRAIN_ICE`, `TERRAIN_LAVA`, etc.) instead of hand-maintaining numeric tables.
36. **Enemy attack intent must be save-gated when available.** `GetSelectedWeapon() > 0` can stay nonzero on non-attacking Vek after movement/re-aim animation, causing Rust's missing-target phantom attack guard to invent false building damage. When `saveData.lua` exposes `iQueuedSkill`, bridge code must derive `has_queued_attack` from `iQueuedSkill >= 0` and only fall back to `GetSelectedWeapon()` when the save field is missing. Regression anchor: Normal run `20260504_210332_088`, mission 7 turn 3, Firefly1 uid `33` falsely threatened B5 and produced a false safety block; fixed in bridge + simulator v47.
37. **Dirty-plan acceptance is single-use.** If the user accepts `--allow-dirty-plan`, that consent applies only to the reviewed plan. If a verify desync forces `auto_turn` to partially re-solve and the new plan predicts grid loss, building loss, mech death, or objective loss, stop with `SAFETY_BLOCKED` and ask again before executing the new line.
38. **Buildings Immune weapon upgrades must be explicit.** The Lua bridge reports the pawn's base SkillList, so powered upgrades that change semantics need save-file overlays plus Rust `WId` support. `Ranged_Artillerymech_A` is Artemis Artillery with direct Grid Building damage set to zero; push/bump collision damage is still physical and can still hurt buildings. If a save loadout contains a new `_A` / `_B` / `_AB` weapon and the overlay drops it, add the upgraded ID before trusting the solve.
39. **Controllable mission allies count if they have weapons.** Friendly non-mech units such as `Archive_Tank` can be READY and player-controlled even when `mech=false` in bridge JSON. If `read` shows a READY friendly with a weapon and the solver omits it, first check whether that weapon has a Rust `WId` mapping. `Deploy_TankShot` / Stock Cannon is a 0-damage projectile with forward push; ignoring it can turn a salvageable tank mission into a false grid-zero safety block.
40. **Dirty frontier before dirty consent.** When a solve safety-blocks and reports `dirty_frontier`, inspect the tradeoff classes before asking to continue. The top raw-score dirty plan may not represent the best strategic compromise; compare options such as `grid_loss`, `mech_loss`, `building_loss`, and `objective_loss` explicitly, especially on Normal where a single dirty Turn 1 can cascade into timeline loss.
41. **Lookahead frontier is diagnostic until promoted.** `project_plan_scenarios` returns bounded plausible next-turn enemy-intent scenarios: base `heuristic_requeue` plus a few high-value building retargets. `lookahead_frontier` in solve output previews worst projected recovery across those scenarios, and `robust_frontier` ranks tradeoffs by current score + worst next-turn score, but neither selects live actions yet. Treat both as evidence for dirty-plan triage and future robust-beam tuning, not as permission to bypass safety.
42. **Rocket Artillery center-kill pushes are weapon-specific corpse bumps.** `Ranged_Rocket` center damage and forward push are simultaneous: if the center target dies, its corpse still resolves the Rocket center push. A dead pushable center target can bump a live blocker; a dead non-pushable center target can still bump static blockers such as buildings/mountains/edge before disappearing. Do not generalize this to every push: Cluster Artillery outer corpse absorption still has a regression test where a dead train corpse does not damage a live adjacent unit. Regression anchors: Easy run `20260506_114649_974`, Storage Vaults turn 1 Pulse mech death and turn 4 Jelly Armor building bump, simulator v55.
43. **Bridge-executed combat does not guarantee Reset Turn is usable.** After `auto_turn` mutates the board through bridge commands, the visible Reset Turn button may hover but refuse to open a confirmation dialog. If a bad bridge plan executes, snapshot immediately, fresh-read/solve from the actual board, and only rely on Reset Turn if the UI visibly opens the confirm prompt.
44. **Time pod recovery UI beats the crossed objective line.** Mission objective rows can look failed after a pod is collected, while the reward flow still shows `Pod Recovered` and the save has `podReward`. Treat the reward screen / save reward state as authoritative. In fallback parsing, numeric save pod state `1` means live/uncollected; recovered state `3` must not be treated as a live board pod.
45. **Manual plan scoring can be invalid-action dirty.** `score_plan` / `replay_solution` are diagnostic tools, not action validators. If a hand-written plan produces an `illegal_*` replay event such as `illegal_leap_landing:x:y:unit`, the plan is impossible in-game and must not be used as dirty-plan consent evidence. Regression anchor: Easy run `20260506_114649_974`, Disposal Vaults turn 4 false clean where Aerial Bombs was hand-scored onto live Spider2 at D2; fixed in simulator v57 by no-oping illegal Leap landings.

## Phase Protocols

Each phase: read → act → verify. Detailed command semantics are in **Game Loop Command Reference** below.

- **NEW_GAME_SETUP** (very start of a new run, before ISLAND_SELECT): Run `python3 game_loop.py achievements --sync` if Steam env keys are present, then `python3 game_loop.py recommend_squad --tags achievement` or initialize with `python3 game_loop.py new_run auto --tags achievement`. On the new-game screen, set **Difficulty: Easy**, ensure **Advanced Edition** content is toggled ON, select the recommended actual squad card, then **Start**. Use **Balanced Roll** only when `recommend_squad` / `new_run --mode solver_eval` / a random-squad achievement explicitly says to. See `feedback_playstyle.md`. When invoking `python3 game_loop.py new_run`, omit `--difficulty` (default 0 = Easy) or pass `--difficulty 0`.
- **ISLAND_SELECT** (after the CEO intro): `python3 island_select.py` picks one of 4 corporations. Click its coord. Click through CEO intro. → ISLAND_MAP.
- **ISLAND_MAP:** `game_loop.py read` → pick mission (prefer bonus objectives for the achievement target) → click mission on map → mission briefing → click preview or start button → DEPLOYMENT.
- **DEPLOYMENT:** `game_loop.py deploy_recommended` → verify PASS for all placed mechs → click visible CONFIRM. If bridge deployment is unavailable, use `game_loop.py read` MCP coords and click 3 recommended tiles manually, then CONFIRM. → COMBAT_PLAYER_TURN.
- **COMBAT_PLAYER_TURN:** `auto_turn --time-limit 10` → dispatch the emitted End Turn click plan or run `click_end_turn` → loop. The next `auto_turn` blocks in Python until the next player turn or mission end. On game_over or empty solution, falls back to screenshot-based reasoning.
- **MISSION_END:** screenshot reward screen → click reward → `snapshot <label>` → ISLAND_MAP (or ISLAND_COMPLETE if all missions done). If the screen visibly shows **Region Secured**, a promotion popup, a reward panel, or the island map while `auto_turn` / `read` keeps returning the previous `combat_player` / `combat_enemy` board from a later turn, treat the bridge as stale and follow this MISSION_END flow; do not keep polling or try another combat command. `cmd_read` cross-checks `saveData.lua` and will now ignore that stale combat bridge board once the save phase is `between_missions` or `mission_ending`; the Lua bridge also dumps `phase="unknown"` immediately on `MissionEnd` so future mission endings don't leave combat JSON behind.
- **SHOP:** appears *only after winning a whole island* (4 missions + finale), not mid-island. Do NOT expect a shop between missions — grid repair opportunities come from time-pod rewards and island completions, full stop. Screenshot when it appears (neither save nor bridge distinguish shop from map). **GRID-FIRST RULE: if Grid Power is below max, buy Grid Power until it reaches 7/7 before considering anything else.** Once the grid is full, the same slot becomes Overpower / +Grid Defense; that is optional, not mandatory, unless the current achievement target explicitly wants Grid Defense or full-grid overpower purchases. With a full grid, shop normally: prefer reactor cores, solver-supported weapons/passives, useful pilots, and achievement-relevant buys. Rationale: `feedback_grid_buy_priority.md`. → ISLAND_MAP (next island) or RUN_END.
- **RUN_END:** `snapshot run_end`. If defeat, analyze critical turns from decision log. Check achievement progress. Start new run with next target.

### Error Recovery

- **Unexpected screen:** screenshot, log to decision log, diagnose visually.
- **State not updating:** `refresh_bridge_state`. If bridge dead, retry save-file verify up to 5× with 1.5s delay.
- **Solve/auto_turn stall:** inspect the latest `recordings/<run_id>/mNN_turn_NN_solve_input.json` first. That file captures the exact Rust payload before solving starts, so reproduce with `itb_solver.solve` / `solve_top_k` / `solve_beam` from it. Do not rely on the next `*_board.json` after a stall; live recovery may have already executed actions or advanced animations, making that board post-action or stale.
- **Grid power = 0:** log, snapshot, analyze.
- **Crash/timeout:** fresh `cmd_read` + `cmd_solve`. Never resume an old solution.

## Game Loop Command Reference

All commands are `game_loop.py <name> [args]`. Each is stateless: read state, compute, output, exit. Session state persists in `sessions/active_session.json`.

**State reading:**
- `read` — Bridge state (primary) or save file (fallback). Prints phase, board, threats, active mechs, deployment zone with MCP coords, env hazards. Auto-records to `recordings/<run_id>/`.
- `status` — Quick summary: turn, grid, mech HP, threats, objectives.
- `verify_action <index>` — Per-action diff: refreshes bridge, diffs actual vs the predicted snapshot captured during `replay_solution`, classifies (click_miss / death / damage_amount / push_dir / grid_power / status / terrain / tile_status / repair_platform / spawn / pod), writes desync to `recordings/<run_id>/failure_db.jsonl`. Never re-solves.
- `verify [index]` — Legacy save-parser-based path (retries 5×, 1.5s each). Superseded by `verify_action` in bridge mode.

**Solving & recording:**
- `solve` — Runs the solver, stores solution in session, prints action sequence. Recording includes structured actions, per-action `ActionResult`, per-action `predicted_states` (input to `verify_action`), predicted post-enemy board, score breakdown, search stats.
- Recordings from `read`/`solve` land in `recordings/<run_id>/m<NN>_turn_<NN>_<label>.json`. Dedup guard prevents duplicate `(mission, turn)` pairs.

**Combat execution:**
- `auto_turn [--time-limit N] [--no-wait] [--max-wait S]` — Full turn via bridge with per-sub-action verification. Polls at entry for `combat_player` phase **and** `active_mechs > 0` (up to `--max-wait` seconds, default 45; disable with `--no-wait`). Returns an MCP click plan for End Turn. On desync, re-solves from actual board with partial mech states (DONE = inactive, MID_ACTION = can_move=false, ACTIVE = full search).
- `click_action <i>` — Pure planner for manual play. Emits a `computer_batch`-ready sequence for ONE mech action (select-tile, optional move, weapon icon, target). Handles dash weapons (skip move click), Repair (click Repair button), passives (no-op).
- `click_end_turn` — Pure planner. Emits a single click on End Turn.
- `recommend_squad [squad|auto] [--achieve ...] [--mode achievement_hunt|solver_eval|random_squad|custom]` — Pure strategist. Uses `data/achievements_detailed.json` to choose a named squad for achievement hunting, or Balanced Roll for solver-eval/random-squad runs.
- `click_balanced_roll` — Pure planner. Emits a single click on the Balanced Roll button on the squad-select screen. Dispatch before clicking Start only when the setup recommendation says Balanced Roll.
- `deploy_recommended` — Bridge deployment helper. Sends `DEPLOY uid x y` for the ranked recommended tiles, verifies placed mech coordinates, and leaves only the visible CONFIRM click for Computer Use.
- `execute <index>` / `end_turn` — Bridge-mode action commands. Used internally by `auto_turn`. In manual play, use `click_action` / `click_end_turn` instead.

**Full-mission automation:**
- `auto_mission [--max-turns N]` — Full mission: auto-deploy → combat loop → mission end. Final turn is force-flushed to failure_db on exit. Falls back to the agent for reward/shop/map screens.

**Analysis & tuning:**
- `replay <run_id> <turn> [--time-limit N]` — Reconstruct Board from a recorded JSON and re-run the solver. Compares new solution with original.
- `analyze [--min-samples N]` — Read failure_db.jsonl, report patterns by trigger / severity / squad / island.
- `validate <old.json> <new.json> [--failures-only] [--time-limit N]` — Compare two weight versions across recorded boards.
- `tune [--iterations N] [--min-boards N] [--time-limit N]` — Auto-tune EvalWeights. Hybrid objective: `mean_fixed_score − 100 * fired_failure_count`.

**Run management:**
- `new_run [squad|auto] [--achieve X Y] [--difficulty N] [--mode achievement_hunt|solver_eval|random_squad|custom] [--tags audit ...]` — Initialize new session. Omit the squad or pass `auto` to let `recommend_squad` choose the achievement-aware setup. Use `--tags audit` / `--mode solver_eval` for environment-audit playthroughs (those failures stay out of the tuner corpus).
- `snapshot <label>` — Save current state for regression.
- `log <message>` — Append reasoning to the decision log.

## Achievement Context

Progress persists in session. Local checklist currently tracks 19/70 earned, 51 remaining across 4 difficulty tiers (Green >40%, Yellow 20–40%, Orange 10–20%, Red <10%).

- Squad-specific achievements need the matching squad — check `data/ref_achievement_strategies.md`.
- Cumulative achievements (reputation, civilians, pilot reuse) accrue across runs.
- Achievement strategies bias solver scoring via `EvalWeights` in `src/solver/evaluate.py`.
- Full checklist: `TODO.md`. Detailed metadata: `data/achievements_detailed.json`.

## Reference Material

Codebase layout, knowledge base tables, and data file inventory live in `docs/reference.md` — read that when you need to find where something is.
