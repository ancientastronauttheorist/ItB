# Task #11 scratch — turn+N projection

Branch: `solver/turn-projection`. Baseline regression green at
`main@856c4d6`.

## What exists today

- `solve` (lib.rs:14) — top-1 single-turn solve
- `solve_top_k` (lib.rs:194) — top-K plans by raw score (Task #3 ship)
- `score_plan` (lib.rs:57) — take a specific plan, apply actions + enemy
  phase, return **score + summary metrics** but NOT the projected board
- `search_recursive` (solver.rs:670) already does apply-plan + enemy-phase
  + `apply_spawn_blocking` + `evaluate` at each permutation's terminal
- `next_turn_threat_penalty` (evaluate.rs:676) — heuristic that penalizes
  enemies-within-reach-of-buildings as a proxy for turn+2 danger

## What Task #10 (beam) needs from #11

```
top_k = solve_top_k(board_t0, k=5)        # exists
for plan in top_k:
    board_t1 = project_plan(board_t0, plan)   # ← Task #11 deliverable
    sub_top_k = solve_top_k(board_t1, k=3)    # exists
    chain_score = plan.score + ff * best(sub_top_k).score
```

So #11 ships **one primitive**: `project_plan(bridge_json, plan_json) -> projected_board_json`.
The returned JSON is round-trippable through `board_from_json` so the
caller can feed it right back into `solve` / `solve_top_k` / another
`project_plan` for depth-N.

## Hard sub-decision: what do enemies do on turn+1?

After `simulate_enemy_attacks` consumes their queued targets, enemies
have no new ones. A real game AI picks new targets at the start of the
next player phase. Without that, turn+1 `solve_top_k` sees no threats
and produces uninformed plans.

**Three options:**

- **A. Project without re-queueing.** Simplest. Turn+1 board has enemies
  but no queued_target_x/y. `solve_top_k` on that board picks
  plans that don't defend buildings because `evaluate` sees no threats.
  Beam ends up preferring "kill everything to exhaustion" — wrong.
- **B. Heuristic re-queue.** After the enemy phase, for each alive enemy,
  pick a queued target: closest Building in Manhattan + move_speed
  range; fallback to closest mech. Not authentic game AI, but makes
  `evaluate` honor real threats at turn+1. **Recommended.**
- **C. Skip re-queue, just reuse `next_turn_threat_penalty`.** Keep
  `queued_target_x = -1` but trust the heuristic to account for future
  danger. Current solver already does this at depth 1; extending to
  depth 2 is free. Problem: `evaluate` at depth 2 still needs real
  threats for `threats_cleared`, `building_coverage`, etc. to score
  turn+2 plans correctly.

**My lean: B.** It's ~40 lines of "pick closest building as next target"
logic in a new `requeue_enemy_attacks` function. Mirrors game behavior
closely enough for scoring purposes (real AI is only marginally
smarter — picks by threat tier, not just distance).

## Deliverable

1. **`rust_solver/src/simulate.rs` (or new file)** — `pub fn project_plan(board, plan, weapons) -> (projected_board, ActionResult)`
   1. Apply each MechAction via `simulate_action`
   2. Run `simulate_enemy_attacks` (env tick + fire tick + attacks)
   3. Run `apply_spawn_blocking`
   4. Run new `requeue_enemy_attacks` (Option B)
   5. Reset all player mech flags for turn+1: `set_active(true)`, `flags |= CAN_MOVE`, `current_turn += 1`
   6. Clear queued attacks that fired
2. **`rust_solver/src/lib.rs`** — `project_plan` pyfunction that returns
   projected-board JSON + action-result summary
3. **`rust_solver/src/solver.rs`** — refactor the terminal block of
   `search_recursive` to call the same primitive (dedup), so search +
   explicit projection agree byte-for-byte
4. **Tests** — ~6 Rust unit tests:
   - projection is deterministic (same inputs → same board)
   - projection round-trips through serde (board_from_json(to_json(project_plan(x))) == project_plan(x))
   - mechs are active again on projected board
   - enemies have queued targets (Option B)
   - spawn blocking applied
   - building HP reflects enemy damage
5. **Python API** — `itb_solver.project_plan(bridge_json, plan_json)`
   exposed. Add a `game_loop.py project_plan` CLI if it helps Task #10
   development; otherwise skip.
6. **No SIMULATOR_VERSION bump.** Pure addition, doesn't change any
   existing prediction path. Refactor in step 3 must be byte-equivalent
   with the current search_recursive terminal, enforced by regression.

## Out of scope (→ Task #10)

- Beam outer loop itself (the for-loop over top_k, the score aggregation,
  the depth-N recursion)
- Any change to `evaluate`'s weights or scaling
- Python-side strategy that *uses* projection for plan selection

## Open question

Does the caller want a single `project_plan` returning one board, or
`project_top_k_plans(board, k) -> Vec<projected_board>` batching the
enemy-phase simulation? Batching saves one enemy-phase pass per plan
but couples the API to beam's specific use. **Starting with single
projection; batching is trivial to add later.**

## Rollback

Pure addition in a new module. If regression breaks in step 3, revert the
dedup refactor and keep the primitive + tests — search_recursive's
terminal and project_plan would then be duplicated logic, which is a
cosmetic loss, not a correctness one.
