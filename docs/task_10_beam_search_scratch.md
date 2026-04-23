# Task #10 scratch — beam outer loop

Branch: `solver/beam-search`. Built on Task #11's `project_plan` primitive.

## Pre-fix: Rust SIMULATOR_VERSION drift

The pilot-passives PR bumped the Python `SIMULATOR_VERSION` 2→3 but did NOT
bump the Rust const at `rust_solver/src/lib.rs:326`. Regression didn't catch
it because `test_regression_corpus.py` calls the Rust solver directly, not
through `cmd_solve`'s `_check_wheel_sim_version` guard — which WOULD fire on
a live run.

First commit on this branch: bump the Rust const to 3. No behavior change;
the guard just starts agreeing with reality.

## What Task #10 needs

Given Task #11's `project_plan(board, actions, spawn_points, weapons) ->
(Board, ActionResult)` primitive, beam search is:

```
beam_chain = solve_beam(board, depth=D, k_per_level=[K₁, K₂, …]):
  level_0 = solve_top_k(board, k=K₁)
  for each plan in level_0:
    projected = project_plan(board, plan.actions)
    level_1 = solve_top_k(projected, k=K₂)
    best_sub = max(level_1, key=score)
    plan.chain_score = plan.score + best_sub.score
  return sorted(level_0, key=chain_score, desc)
```

`evaluate`'s `future_factor` already discounts per-turn within a single
evaluation, so at the beam level we can **sum raw scores** without extra
discount. The `score_delta` harness from Task #11 reported aggregate |proj − actual|
score gaps ~230k on the full corpus, with well-predicted triples at 3k–66k.
That's the noise floor beam has to clear to be useful.

## Design decisions

### Depth & K
- **Depth = 2** first ship. Every level multiplies compute by ~K. Depth 3
  would be 5 × 5 × 5 = 125 solves, each ~1s — 2-minute turns. Deferred.
- **K_1 = 5, K_2 = 3**. At depth 2 that's 5 top plans × 3 sub-plans = 15
  solves + 5 projections. ~15–20s wall-clock on the Rust side. Matches
  `--time-limit 10` budget with room.

### Time budget
- Top-level `time_limit` param is the TOTAL wall-clock budget. Split
  roughly 40/60 between level 0 (broad search) and level 1 (narrower
  per-chain).
- Fall back to single-turn `solve_turn` if we run out of budget before
  level 0 finishes (graceful degradation, never worse than today).

### Chain scoring
- `chain_score = level_0_score + best_level_1_score` (no discount — future_factor handles it inside each evaluate).
- No penalty for chains where level 1 finds no plan (game-over or no
  actions possible). Just score level 0 alone — represents "mission ends
  here, we only care about turn 1."

### Edge cases
- `project_plan` applied to a final-turn board produces a board at
  `current_turn = total_turns + 1`. Level 1 solver should return no
  actions (no turns left). Treat as chain_score = level_0_score.
- If projected board has zero alive mechs, level 1 returns no actions —
  same fallback.
- Non-determinism: `solve_turn_top_k` is deterministic per Task #3. Beam
  must preserve that — test byte-level determinism at the chain level.

## Deliverable

1. **`rust_solver/src/beam.rs`** — new module.
   - `pub struct BeamChain { level_0: Solution, level_1_best: Option<Solution>, chain_score: f64 }`
   - `pub fn solve_beam(board, spawn_points, depth, k_per_level, time_limit, weights, disabled_mask, weapons) -> Vec<BeamChain>`
2. **`rust_solver/src/lib.rs`** — pyfunction `solve_beam(bridge_json, depth, k, time_limit) -> json`.
3. **Rust unit tests** in `beam.rs`: depth 1 equivalent to `solve_top_k`, depth 2 produces chains sorted by chain_score desc, final-turn board returns level_0 only, determinism.
4. **Integration test `tests/beam_vs_top1.rs`** — walk recordings, run beam at depth 2 and single-turn solve on same board, report how often beam picks a different plan than top-1, and when it does, whether the chosen chain's score is higher. Expected: beam differs from top-1 on ~20–40% of turns; on those, chain score > top-1 score by construction.
5. **Python API smoke test** — call `itb_solver.solve_beam` from pytest.
6. **No SIMULATOR_VERSION bump** — pure addition.

## Out of scope

- `cmd_solve` / `game_loop.py` integration. Beam can be exposed to Python
  but not plumbed into the default `auto_turn` path until we've
  benchmarked live plan quality. Keep that behind a `--beam` flag in a
  follow-up PR.
- Dynamic K per level (e.g., prune to K=2 if level_0 scores are tightly
  clustered). Start static.
- Parallelizing level 1 solves across chains. Each sub-solve is already
  parallel internally via rayon; adding another layer risks oversubscription.
- Depth ≥ 3.

## Risks

- **Compute**: 15 solves × ~1s = 15s per turn. Could be slow on busy
  boards. Mitigation: budget falls back cleanly.
- **Noise**: turn+1 evaluation uses the heuristic-re-queued board from
  project_plan, not real game AI. The sub-solver might pick a "good
  defensive move" against a heuristic-guessed threat that doesn't
  materialize. Mitigation: `evaluate`'s future_factor already damps
  turn+1 scoring heavily; the beam signal is additive, not overriding.
- **Regression corpus**: the 277-board corpus is single-turn; beam
  doesn't touch any of it. Regression stays green by construction.

## Success criteria

- Regression 277/277 + Python failure_db PASSED (must not break existing)
- Beam returns plans on every recorded board in the corpus
- Beam picks a plan ≥ top-1's plan (chain_score ≥ level_0 only) on 100%
  of boards — by construction, since chain_score ≥ level_0 for all K₂ ≥ 1
- Beam picks a DIFFERENT plan than top-1 on some subset (diagnostic, not
  a gate — 0% would be suspicious, 100% would mean top-1 is always wrong)
