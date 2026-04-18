# Regression boards for weapon overrides

Every entry committed to `data/weapon_overrides.json` must have a matching
regression board in this directory. The test at
`tests/test_weapon_overrides_regression.py` enforces the invariant:

1. Each override's `weapon_id` has at least one JSON file here matching
   `<weapon_id>_<case>.json`.
2. Running `itb_solver.solve` on the board's `bridge_state` produces a
   **different solution** with the override applied vs without. This
   proves the override actually changes solver behaviour — an override
   that has no observable effect is rejected (probably a typo on
   `weapon_id` or a field the solver doesn't branch on).

## Board file format

```json
{
  "weapon_id": "Ranged_Defensestrike",
  "case": "baseline_miss",
  "bridge_state": { ...full bridge JSON as produced by game_loop.py read... },
  "expected_delta": "damage_changes_kill_count",
  "note": "Cluster Artillery fires on a 2HP Firefly: rust says 0 damage, Vision says 1. With the override the mech kills the Firefly in one shot; without it, the firefly survives."
}
```

- `weapon_id` (required) — matches the override entry.
- `case` (required) — human-readable short tag, becomes the filename suffix.
- `bridge_state` (required) — full bridge JSON. Any recorded `m00_turn_NN_board.json`
  works as a starting point; drop the outer wrapper and keep just the
  `data.bridge_state` dict.
- `expected_delta` (optional, informational) — describes the intended
  observable change. The test doesn't parse this, but future versions
  may tighten enforcement.
- `note` (optional) — free-form.

## Adding a new board

1. Reproduce the bug in-game, capture the turn's bridge state via
   `game_loop.py read` (look under `recordings/<run_id>/`).
2. Trim down to the minimal unit set that still triggers the solver
   divergence. Buildings, mech HP, enemy queue — leave everything load-bearing.
3. Drop the file here as `<weapon_id>_<case>.json`.
4. Run `pytest tests/test_weapon_overrides_regression.py` before
   `game_loop.py review_overrides accept <idx>`.
