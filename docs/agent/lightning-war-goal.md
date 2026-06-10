# Lightning War Bridge-First Goal Prompt

Build a reliable, bridge-first Lightning War automation path for Into the
Breach.

## Objective

Create or replace the Lightning War automation with a Python runner that can
autonomously finish the first two Corporate Islands in under 30 minutes with
the Blitzkrieg squad.

Reliability comes before raw speed:

- no pilot death or mech destruction at mission end
- no grid collapse, HQ loss, or defeat
- no failed-objective surprises
- no unresolved research, safety, threat-audit, post-enemy, or desync gates
- no manual combat decisions

After a reliable two-island baseline exists, add a speed mode that reduces
latency while preserving the same proof and stop-sign discipline.

## First-Principles Design

Treat the run as a game-state transaction system, not primarily as visual UI
automation.

The Lua bridge and Rust solver are the source of truth whenever they can prove
state. Screenshots and CV are fallback/witness tools for states that the bridge
does not yet expose.

The runner should ask:

1. What state does the bridge prove?
2. What irreversible action is being considered?
3. Are the preconditions for that action proven?
4. Can the solver model the consequences?
5. Is the action acceptable under the Lightning War loss policy and time budget?

If any answer is uncertain, the runner must choose another proven path, recover
state, or stop with evidence. It must not blind-click or improvise.

## Bridge-First Control Model

Prefer bridge-native state and commands for:

- active combat state
- phase, turn, grid, difficulty, squad/loadout, and heartbeat
- deployment zones
- mission id and mission objectives
- island-map mission slates from `GAME.Missions`
- units, weapons, queued attacks, terrain, spawns, and environment danger
- deploy, move, attack, repair, speed-mode, and other bridge-safe actions

Use screenshots/CV only where bridge coverage is absent or insufficient:

- main menu and new-run setup
- first island-selection screen before a bridge island map exists
- mission preview/start UI until a bridge-native start command exists
- reward, shop, leave-island, and confirmation panels until bridge-native
  commands exist
- crash dialogs, focus issues, modloader failures, achievement toasts, and
  unexpected screens

When screenshot/CV pain repeats, prefer adding bridge fields or commands over
adding more fragile image logic.

## Generality Requirement

Do not hardcode a single favorite island, mission list, or route. The runner
must be able to reason over any available path.

Build a route graph:

```text
main menu
-> verified Blitzkrieg setup
-> island selection
-> island mission slate
-> mission candidate
-> deployment
-> combat
-> reward/shop/continue
-> next mission or HQ
-> second Corporate Island complete
```

At each node, enumerate all available choices, score them, and take the best
provable path under the current policy. If no path is provable, stop with a
specific missing-contract report.

Mission choices should not be categorized as simply good or bad. Each mission
should resolve to one of:

- `PROVABLE_SAFE`
- `PROVABLE_WITH_ALLOWED_OPTIONAL_FAILURE`
- `PROVABLE_BUT_SLOW`
- `UNPROVABLE_NEEDS_BRIDGE_OR_SOLVER_WORK`
- `FORBIDDEN_PRIMARY_RISK`

Generality comes from adding mission contracts and bridge/solver coverage, not
from taking unsupported risks.

## Lightning War Loss Policy

Lightning War does not require perfect islands. The runner may deliberately
ignore or fail optional objectives only when the policy and evidence say that is
acceptable.

Hard forbidden outcomes:

- pilot death
- mech destroyed at mission end
- grid collapse
- Corporate HQ loss
- defeat or abandoned live timeline after irreversible progress
- unresolved desync or stale-state ambiguity
- unmodeled primary objective loss
- any terminal screen that contradicts the expected run state

Potentially allowed outcomes, only when predicted and logged:

- failed bonus objective
- missed time pod
- imperfect island reward
- low reputation
- non-terminal grid damage
- ugly but safe tactical position

"Failed objective surprise" remains a blocker. A planned optional failure is a
different state from discovering a failure on the reward screen.

## Mission Contracts

Create or maintain a mission contract registry. Each contract should describe:

- mission id
- primary objectives and terminal loss conditions
- optional objective ids and whether Lightning War may ignore them
- required bridge fields
- required solver checks
- known simulator coverage
- known bridge/parser hazards
- expected time cost
- route-policy tags
- recovery evidence required after ambiguity

The route planner should score every visible mission from the bridge island map
or verified preview using these contracts.

Avoid-list behavior should be policy-derived, not hardcoded as permanent truth.
A mission is skipped because it is currently slow, risky, or unprovable; once
bridge and solver coverage improve, the same mission can become playable.

## Current Known Hurdles

Address these explicitly:

1. Existing mission previews can remain open after a rejected route probe.
   Implement a guarded existing-preview reselect path only for route-start
   modes designed for it. Plain preview modes must still block before clicking
   another region.
2. Route preview, Start Mission, and deployment must each have separate proof.
   Preview OCR alone is not Start authority in speed mode.
3. Stale bridge heartbeat outside a verified pause menu, stale heartbeat that
   persists after unpausing, or stale combat JSON must trigger fresh state
   recovery. Never resume an old solve after crash, timeout, desync, or reload.
4. Computer Use may be unavailable. If repo/macOS click helpers are used as a
   fallback, log that fallback and keep the click path proof-gated.
5. The old Lightning Conductor/Lightning War code may contain useful pieces, but
   preserving it is not required. Prefer a smaller observable state machine.
6. Live proof runs must not repeat the same blocker for hours. If the same
   blocker repeats three times, or a live run spends about 30 minutes without a
   new milestone, stop, summarize evidence, patch/test, and then resume.

## Preferred Bridge Extensions

Where practical, reduce screenshot dependence by adding bridge-native support
for outer-loop actions:

- `screen_kind`: main menu, setup, island_select, island_map, mission_preview,
  deployment, combat, reward, shop, island_complete, defeat, unknown
- `START_MISSION region_id expected_mission_id`: start only when the current
  mission slate matches the expected mission
- `SELECT_ISLAND corp_id`: commit only when the intended corporation is proven
- `SHOP_STATE` and `SHOP_BUY item_id`: reputation, grid, cores, weapons, pilots,
  passives, and buy results
- `REWARD_STATE` and `CHOOSE_REWARD choice_id`
- `NEW_RUN squad difficulty advanced_content`, if feasible
- bridge-native End Turn if the engine path can be made reliable

Until those exist, keep CV/menu helpers narrow, evidence-rich, and
preconditioned.

## Milestone 1 - Discovery And Design

Map the relevant code paths:

- `game_loop.py`
- `src/loop/`
- current Lightning runner/conductor code
- `src/strategy/`
- `src/bridge/`
- `rust_solver/`
- CV/menu helpers
- setup verification
- deployment helpers
- reward/shop/island navigation
- current tests and snapshots

Deliver a short implementation plan identifying reusable pieces, brittle paths,
missing bridge fields, mission-contract gaps, and the minimal reliable runner
design.

## Milestone 2 - Baseline Two-Island Runner

Implement a Python runner that starts from the main menu and autonomously:

1. Starts or continues the correct Lightning War attempt.
2. Verifies Blitzkrieg, Easy difficulty unless explicitly changed, Advanced
   Content assumptions, and window focus before Start.
3. Enters a corporate island and scores all available mission candidates.
4. Starts missions only with proven mission identity and acceptable contract
   status.
5. Handles deployment and confirmation with bridge-backed proof.
6. Completes combat with bridge-backed solver automation.
7. Uses fresh read plus solve after crash, timeout, stale heartbeat, desync, or
   recovery.
8. Detects victory, reward, island map, shop, corporate transition, defeat/KIA,
   failed objective, and unexpected screens.
9. Shops conservatively: grid safety first, then cores or clearly modeled
   high-value items. Skip unknown items.
10. Finishes the first two Corporate Islands without manual help except
    explicit stop-sign evidence requests.

## Milestone 3 - Recovery And Evidence

Add robust logging, screenshots, snapshots, and focused tests for:

- existing-preview route reselect
- preview mismatch, veto, unverified mission, and unassigned multi-region slate
- stale bridge heartbeat
- bridge/CV disagreement
- reload or main-menu recovery
- reward/shop misclassification
- deployment ambiguity
- island-map ambiguity
- combat desync
- solver timeout
- research gates
- safety and threat-audit blocks
- post-enemy blocks
- unexpected terminal screens

Prefer focused tests and replay checks over long live retries.

## Milestone 4 - Speed Mode

Only after the baseline can reliably complete two corporate islands, add speed
mode.

Speed mode may:

- reduce unnecessary screenshots
- reduce sleeps and polling intervals where state proof remains reliable
- cache stable UI coordinates/templates
- use bridge fast mode
- tune solver time limits by turn difficulty
- skip diagnostics on clean, already-proven paths
- add phase, mission, turn, island, and shop timing logs

Speed mode must not:

- blind-click unknown UI
- bypass stop signs
- treat OCR as sufficient Start authority without policy approval
- ignore stale bridge heartbeat while the game should be ticking; stale
  heartbeat is expected while visibly paused, but must refresh after unpause
- continue after repeated identical blockers
- make manual combat decisions

## Build And Test Discipline

Follow the project agent rules:

- Rebuild and reinstall `itb_solver` after Rust solver edits.
- Use `cargo test --no-default-features` for focused Rust tests.
- Do not run repo-wide `cargo fmt` during tactical fixes.
- If `src/bridge/modloader.lua` changes on macOS, run
  `bash scripts/install_modloader.sh` and restart the game.
- Stage only relevant files.
- Commit and push verified solver/simulator diagnosis fixes before resuming
  achievement play unless the user explicitly pauses or git state blocks it.

If git staging or commit is blocked by an active lock/process, do not force
unrelated cleanup silently. Report the blocker and stage/commit only when safe.

## Deliverables

1. Bridge-first baseline two-island autonomous runner.
2. Supporting CV/menu/navigation helpers only where bridge coverage is absent.
3. Mission-contract registry and route scoring that can handle any available
   path by proof status.
4. Reliability logs, evidence, snapshots, and focused tests.
5. Speed-optimized Lightning War mode.
6. Short docs for baseline and speed commands, assumptions, recovery paths,
   mission-contract states, and live-run stop/report rules.
