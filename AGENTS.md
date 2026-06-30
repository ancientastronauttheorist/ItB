# Into the Breach Achievement Bot Agent Guide

This is the fast-load guide for autonomous Into the Breach achievement runs.
The old long-form field manual was split on 2026-05-25 into focused docs under
`docs/agent/`.

## Read First

- `docs/agent/live-runbook.md` - phase flow, command reference, UI/click rules,
  session locking, and live shell/search hygiene.
- `docs/agent/safety-gates.md` - research gates, diagnosis loop,
  investigations, dirty-plan consent, post-enemy blocks, and threat audits.
- `docs/agent/solver-reference.md` - architecture, Rust build/test discipline,
  core mechanics, simulator rules, bridge/parser rules, and weapon case law.
- `docs/agent/achievement-playbook.md` - run setup, achievement targeting,
  shop priorities, and named-achievement exceptions.
- `docs/agent/rule-index.md` - historical numbered rule lookup.
- `docs/agent/legacy-full-guide.md` - verbatim pre-cleanup `AGENTS.md`.

Existing design docs remain authoritative for their domains:
`docs/reference.md`, `docs/lua_bridge_architecture.md`,
`docs/self_healing_loop_design.md`, `docs/diagnosis_loop_design.md`,
`docs/solver_goal_principles.md`, and `docs/env_hazards_by_island.md`.

## Git Workflow

Development alternates between this macOS laptop and a Windows desktop, so
always sync from GitHub before starting project work. Check status, stay on
`main`, and run `git pull --ff-only` before editing, testing, committing, or
resuming live achievement play. If local dirty files block the pull, inspect
and protect the dirty work before resolving the sync; never overwrite or revert
user changes just to pull.

Do not create feature branches for this project. Do all work, commits, and
pushes directly on `main`, then push `main` back to GitHub when the requested
change is complete.

## Project Goal

Earn all 70 Into the Breach achievements autonomously on macOS and Windows while
the user watches in real time. Combat state comes from the Lua bridge through
the platform bridge directory (`/tmp/` on macOS, profile-local `itb_bridge/` on
Windows).
Combat actions go through the bridge; deployment, menus, shop, rewards, and
island navigation use Codex Computer Use clicks.

Steam App ID: `590380`.

The user now runs Steam in offline mode during achievement play. Do not rely on
live Steam/API sync as the first proof that an achievement unlocked. Use the
Into the Breach log at `~/Library/Application Support/IntoTheBreach/log.txt`
and local profile/cache evidence instead: look for `Set Steam Achievement
<achievement_id>` lines, map the ID to the achievement name in the local
metadata or Steam client cache, and record any profile flag corroboration. The
log has no per-line timestamps and may replay already-earned achievements on
restart, so report what it proves precisely: usually that the game/Steam client
recognized the achievement during that launch, not necessarily the exact popup
moment.

After editing `src/bridge/modloader.lua` on macOS, run:

```bash
bash scripts/install_modloader.sh
```

Then restart the game.

On Windows, install the same `src/bridge/modloader.lua` into the ITB-ModLoader
location used by the game, then restart the game.

## Architecture

- Layer 0, game loop: `game_loop.py` plus `src/loop/`.
- Layer 1, state extraction: `src/bridge/` first, `src/capture/save_parser.py`
  as fallback.
- Layer 2, model: `src/model/` is the Python board/unit/weapon source.
- Layer 3, solver and simulator: `rust_solver/` is the only solver and the
  only simulator. The PyO3 extension is `itb_solver`.
- Layer 4, strategy: `src/strategy/` chooses weights, squads, islands, shops,
  and achievement targets.

`src/solver/simulate.py` is gone. Simulator fixes belong in `rust_solver/src/*.rs`
unless a bridge/parser/model bug is proven.

## Build And Test

Rebuild after editing any Rust solver file:

```bash
cd rust_solver && maturin build --release && \
  pip3 install --user --force-reinstall target/wheels/itb_solver-0.1.0-cp39-cp39-macosx_11_0_arm64.whl
```

If `maturin` is not on `PATH`, use `python3 -m maturin build --release` from
`rust_solver/`, then run the same `pip3 install`.

Focused Rust tests in this PyO3 crate need:

```bash
cargo test --no-default-features
```

If cargo hits a rustc incremental-compilation ICE, rerun with
`CARGO_INCREMENTAL=0`. If cargo or maturin stalls while reading generated
fingerprint files, stop it, remove only the affected generated
`rust_solver/target/{debug,release}/.fingerprint` directory, and rerun.

Do not run repo-wide `cargo fmt` during tactical fixes. This tree is not
globally format-clean.

## Default Combat Loop

Default combat command:

```bash
python3 game_loop.py auto_turn --time-limit 10
```

`auto_turn` reads the board, solves, executes every mech action through the
bridge, verifies after each sub-action, re-solves on desync when possible, and
emits an End Turn click plan. It waits at entry for both
`phase == combat_player` and `active_mechs > 0`.

The Lua bridge heartbeat is written from mission `BaseUpdate`. A visible pause
menu can suspend that tick and make the heartbeat stale; this is expected while
paused and is not by itself a bridge failure. Before any bridge combat command,
unpause or otherwise return to a ticking game state and wait for a fresh
heartbeat. If the heartbeat remains stale after unpausing, or goes stale during
a bridge command, recover from a fresh `read` plus `solve`.

Typical turn rhythm:

```text
auto_turn -> click emitted End Turn batch -> auto_turn -> click emitted End Turn batch
```

Use `click_action`, `verify_action`, and manual combat tile clicks only when the
bridge is unavailable or an explicit safety/manual protocol calls for it.
Never call bridge sub-action commands such as `move_mech`, `attack_mech`,
`skip_mech`, or `repair_mech` directly during ordinary play.

## Coordinates And UI

- Bridge `(x, y)` to visual tile: `Row = 8 - x`, `Col = chr(72 - y)`.
  Example: bridge `(3, 5)` is visual `C5`.
- Use A1-H8 visual notation in communication.
- Click tile centers, not sprites.
- No keyboard during combat.
- End Turn is the only routine combat UI click. Use the emitted
  `codex_computer_use_batch` or the per-click `window_x` / `window_y`, not
  legacy global coordinates. The calibrated End Turn offset is `(126, 120)`
  window-relative.
- For novel UI, use hover -> screenshot -> click. End Turn and calibrated
  combat tile clicks are exempt.
- Prefer `game_loop.py read` over screenshots for combat state. Reserve
  screenshots for novel UI screens, reward/shop/defeat screens, and unexpected
  state.

## Hard Invariants

1. Run session-touching `game_loop.py` commands one at a time. Never put them in
   `multi_tool_use.parallel`, chain them with `&&`, pipe them to filters, or run
   them beside screenshots/UI inspection.
2. Always verify after each mech action. `auto_turn` does this automatically.
3. After a crash, timeout, stale heartbeat outside a verified pause menu, stale
   heartbeat that persists after unpausing, or desync recovery, start from a
   fresh `read` plus `solve`; never resume an old solution. A stale heartbeat
   while visibly paused is expected; unpause and wait for a fresh heartbeat
   before bridge combat commands.
4. Trust the solver by default. Do not override it unless it times out, returns
   empty, or an explicit dirty/manual protocol authorizes the exact line.
5. Use all mech actions every turn unless the solver or a safety gate says
   otherwise.
6. Never voluntarily move onto ACID.
7. Buildings and objective survival outrank threats, which outrank kills, which
   outrank spawn blocking unless a named achievement changes the priority.
8. Save data is stale mid-turn. Trust the bridge for live combat. On visible
   reward/KIA/failed-objective screens, trust the screen.
9. Effective upgraded weapons must come from save overlays and must have Rust
   `WId` plus `known_types` coverage before solving.
10. Controllable mission allies with weapons count as player actors even when
    `mech=false`.
11. Simulator semantic changes require `SIMULATOR_VERSION` discipline: archive
    the old failure DB, bump both Rust/Python version pins, rebuild/install,
    run a focused proof, and run the broader regression harness when timing
    allows.
12. Process mistakes should update the narrowest focused doc under `docs/agent/`.
    Touch this top-level file only for global rules every agent must load.

## Stop Signs

Stop before further combat commands or End Turn clicks when any of these appear:

- `requires_research: true` or `RESEARCH_REQUIRED`.
- `INVESTIGATE` or `INVESTIGATE_POST_ENEMY`.
- `THREAT_AUDIT_BLOCKED`.
- A persistent `post_enemy_block`.
- `SAFETY_BLOCKED` that has not had its dirty frontier reviewed.
- A post-action desync that leaves the board uncertain.
- Visible reward text showing KIA, failed objective, Region Secured mismatch, or
  another terminal outcome that contradicts the solver.

Research gate protocol: snapshot, run `research_next`, capture/submit the
requested evidence, attach community notes if requested, resolve stale known
types with `research_resolve`, and repeat until no work remains.

Diagnosis protocol: drain between turns, one entry per call unless the user asks
to clear the queue. Run dry-run before applying an agent proposal. If a concrete
diagnosis fix applies, verify it, rebuild Rust if needed, run focused proof and
regression when possible, then stage only the relevant fix/regression/doc files,
commit, and push before resuming achievement play. Do not leave verified
solver/simulator fixes sitting uncommitted through the next mission unless the
user explicitly asks you to pause.

Dirty-plan protocol: inspect the dirty frontier first. The user has granted
standing consent to run reviewed dirty lines when there is no desync,
investigation gate, unresolved research, threat-audit block, persistent
post-enemy block, or board uncertainty. A plain `--allow-dirty-plan` is
insufficient; rerun only with the exact single-use `--dirty-consent-id` for the
reviewed line, plus any required broad dirty flag for that exact loss class.
Timeline collapse is not covered by standing consent. The documented
final-cave resist emergency needs explicit live user authorization for the exact
resist line before spending the token.

## Achievement Setup

For normal achievement hunting, sync and target an unfinished squad:

```bash
python3 game_loop.py achievements --sync
python3 game_loop.py recommend_squad --tags achievement
python3 game_loop.py new_run auto --tags achievement
```

Defaults:

- Ordinary squad achievements: Easy, `--difficulty 0`, Advanced Edition ON.
- Hold the Line: Normal, `--difficulty 1`, unless continuing an existing Easy
  timeline by explicit choice.
- Hard Victory: Hard, `--difficulty 2`, Advanced Edition ON, chosen target
  squad. Do not fall back to another difficulty unless the run target changes.

Before pressing Start on a new run, require `verify_setup --difficulty <target>`
to pass and confirm the screenshot is actually focused on Into the Breach.

Active Hold the Line exception: after deployment or End Turn, poll with
standalone `read` until `phase == combat_player` and `active_mechs > 0`; if
`spawn_points >= 2`, inspect spawning tiles and run spawn-banking triage before
`auto_turn`.

Shop rule: if Grid Power is below max, buy Grid Power until `7/7` before cores,
weapons, pilots, or leaving the island. Use Undo All if you bought something
else first.

## Core Mechanics

The solver enforces the full rules in `docs/agent/solver-reference.md` and
`data/ref_game_mechanics.md`. High-risk reminders:

- Water and chasms kill non-flying ground units. Lava kills ground units and
  sets flying units on Fire.
- Push into blockers causes bump damage. Push/bump/fire/blocking damage ignores
  Armor and ACID.
- Weapon damage is reduced by Armor and doubled by ACID.
- Frozen units are invincible and immobilized; any damage unfreezes without
  applying damage.
- Smoke prevents attacks and repair.
- Webbed units cannot move but can still attack. A blocked push does not clear
  web.
- Environment danger normally ticks before Vek attacks. `Mission_Tides` is the
  exception: queued Vek attacks land before the wave advances, and flying units
  on tide tiles take 1 damage. `environment_danger_v2` entries are
  `[x, y, damage, kill_int]`; `kill_int=1` means lethal for grounded units.

## Command Cheat Sheet

- `read` - live bridge state first, save fallback.
- `status` - quick session summary plus persistent blocks.
- `solve [--candidate-rank N]` - solve and record without executing.
- `auto_turn [--time-limit N]` - default full combat turn.
- `click_end_turn` - pure End Turn click planner.
- `deploy_recommended` - bridge deployment helper; click visible CONFIRM after.
- `research_peek` - read-only research queue view.
- `resolve_post_enemy_block --reason "<specific cause/fix>"` - clear a
  persistent post-enemy block only after understanding it.
- `snapshot <label>` - save current state for regression.
- `log '<message>'` - append a decision note. Quote the message as one shell
  argument, especially if it contains punctuation.

When uncertain about a command shape, inspect parser/help in a standalone
command first, then call only supported flags.

## Reference Material

Use `docs/agent/rule-index.md` to find historical rule numbers and regression
anchors. Use `docs/reference.md` for codebase layout, knowledge base tables, and
data file inventory.
