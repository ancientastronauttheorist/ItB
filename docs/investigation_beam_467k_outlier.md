# Investigation: the −467k outlier from `beam_vs_top1.rs`

## TL;DR

Not a bug. The outlier is beam correctly detecting a phantom-turn-+1
catastrophe on a malformed overtime board. `project_plan` and
`evaluate` are both behaving as designed — the weird signal comes from
bridge-side mis-reporting of `total_turns` for this particular
mission.

No code change. Filing this note so future readers don't re-open the
investigation when they see the same shape in a new run.

## Symptom

`rust_solver/tests/beam_vs_top1.rs` initial run (before merging
beam to main) reported one line:

```
[run=20260411_135608_323 t=03] same=1 top1=41449 beam_lvl0=41449 bonus=-467435 chain=-425986
```

Top-1 rated the board +41k. Beam level_0 picked the same plan. But
beam's level_1_best was −467k, producing a chain score of −425k and
dragging the corpus-wide `avg_level_1_bonus` to −95k.

## Board state

From `recordings/20260411_135608_323/m00_turn_03_board.json`:

- `current_turn = 3`, `total_turns = 2` ← **overtime, not a valid
  mid-mission state**
- `grid_power = 2 / 7`
- 3 mechs (one already dead: PunchMech hp=0), 6 enemies, 5 with
  queued attacks
- Threats: Leaper (3 dmg) + Scarab (artillery) both queued on (2, 2);
  3 Hornets on edge buildings

Trace across the whole run shows `total_turns=2` for turn_00 / turn_01
/ turn_02 / turn_03 — the bridge was mis-reporting mission length
throughout. Either a Mission_* subclass with non-standard total_turns
handling, or a save-file corruption. The mission actually ran at
least 3+ player turns; bridge said 2.

## Why top-1 reports +41k

- `future_factor(3, 2, *) = 0.0` (`total_turns.saturating_sub(combat_turn + 1)` = 0)
- Every FF-scaled weight collapses to its floor — including the
  `next_turn_threat_penalty` heuristic that would normally flag
  "enemy can reach building"
- Core weights (building_alive, building_hp, grid_power, enemy_hp_remaining)
  still fire. Score reflects post-turn-3 state: 4 buildings alive, grid=2,
  2 enemies dead from the mech plan → +41k
- Top-1's only forward-looking signal was silenced by ff=0. So its
  score is structurally blind to multi-turn outcomes on overtime boards.

## Why beam reports −467k

- `project_plan` applies the plan, runs the turn-3 enemy phase
  (grid stays at 2 — threats hit non-grid-reward buildings), clears
  fired queued targets, `requeue_enemies_heuristic` assigns new ones
  (closest building in reach), bumps `current_turn` to 4
- Sub-solve runs another mech phase + another enemy phase on the
  projected board. This second enemy phase picks grid-reward
  buildings via the heuristic re-queue, drops grid to 0
- `evaluate` on grid=0 returns a large negative (game-over signal
  from building/grid terms + `mech_sacrifice_at_critical`)

Beam is numerically correct given its inputs. But its inputs represent
a *phantom* turn+1 — in the real game, this mission should have ended
at turn 2.

## Why this is not a bug in beam / project_plan

Three candidates considered and rejected:

1. **"project_plan shouldn't increment current_turn past total_turns"**
   — `future_factor` already treats any turn beyond `total_turns - 1`
   as ff=0. Clamping `current_turn` in `project_plan` would not change
   any scoring. The phantom enemy phase still runs and still drops grid.
2. **"beam should refuse overtime boards"** — Beam has no clean way to
   identify "this mission has ended" short of trusting `total_turns`,
   which is exactly what's wrong here. And in a real overtime mission
   (some mission types legitimately run past total_turns), beam's
   projection IS useful.
3. **"the heuristic re-queue is over-aggressive"** — On normal boards
   the heuristic is conservative-ish (closest Building, skips
   Webbed/Frozen/Smoked). On this board it happens to pick
   grid-reward tiles because those are the closest surviving
   buildings to the surviving enemies. Real game AI would likely
   do the same.

## Actual root cause

**Bridge-side:** `total_turns` was mis-reported as 2 for this
mission. Corpus-wide sweep confirms a time-bounded bug that was
fixed before I touched this codebase:

```
date        boards   bad  ratio
20260410        10     0     0%
20260411        44    10    23%
20260412        28     8    29%
20260413        33     8    24%
20260417         5     0     0%   ← fixed
20260418         5     0     0%
20260420        15     0     0%
20260421        75     0     0%
20260422        15     0     0%
```

26 anomalous boards across 15 runs, all concentrated in April 11-13.
Clean from April 17 onward. Whatever bridge-side fix landed between
the 13th and the 17th eliminated the mis-report — modern runs don't
produce this outlier pattern.

We don't have a board_04 file for this run, so we can't compare beam's
projection against ground truth. The `m00_mission_summary.json` is
empty (all-zeros, outcome=null), suggesting the mission terminated
mid-turn without producing a summary — consistent with a mission
that the bridge silently ended.

## Implications for the harness

`beam_vs_top1.rs` averages across all processed turns. One outlier
with bonus = −467k drags the mean toward negative even when other
boards score well (the 5 non-outlier triples had bonuses in the
−50k to +125k range).

Two options for the harness:

- **Keep as-is** — report the outlier, flag it in output, let readers
  interpret. Current approach.
- **Filter overtime boards** — skip triples where
  `current_turn >= total_turns`. Would smooth the aggregate but
  might hide a genuine overtime scoring bug if one ever appears.

For now: keep as-is. The single outlier is clearly labelled by run
and turn in the per-line output; the aggregate is honest.

## Recommendation

Close the investigation. No code change. If a SECOND outlier like
this appears in future harness runs and shares the `total_turns`
mis-reporting pattern, investigate the bridge side
(`src/bridge/modloader.lua::total_turns` extraction logic).

If an outlier appears on a board where `current_turn < total_turns`,
reopen — that would be a real projection bug.
