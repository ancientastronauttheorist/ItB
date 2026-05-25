# Hard Rusting Hulks Final Cave Retrospective

Run: `20260513_230944_542`  
Mission: `m24`, `Mission_Final_Cave`  
Outcome: Victory screen reached on 2026-05-16. Hard Victory and Stormy Weather were both present after the Steam achievement sync.

## Mission Shape

We entered the cave at 6/7 grid with Rusting Hulks alive, but the squad was still closer to a 2-island kit than a Hive-ready kit. Jet/Rocket/Pulse had enough control to survive, not enough spare tempo to make the final cave comfortable. That run-level choice mattered more than any single turn.

The core lesson: Hard Rusting Hulks should usually take island 3 unless the grid is near-full and the kit can answer four simultaneous building/pylon threats without leaning on grid defense.

## Turn Review

### Turn 1

Plan played:

- Jet `E6 -> B5`, Aerial Bombs at `B3`
- Rocket `D5 -> F6`, Rocket Artillery at `F4`
- Pulse `E5 -> G5`, Repulse at `G5`

Outcome: grid stayed 6/7, bomb survived, and the immediate threats were covered. The hidden cost was positional: Rocket ended at `F6`, Pulse at `G5`, and Jet's attack path left us tied to next-turn danger geometry. The next player turn opened with hazards on `B3`, `F6`, and `G5`.

What could have been better: when final-cave grid is not full, the solver should treat multiple mechs ending on next-turn danger as action-economy debt, even if the current post-enemy prediction is clean. This should be a soft frontier/weight signal, not a hard block, because sometimes standing on danger is correct.

### Turn 2

Plan played:

- Jet `B3 -> B6`, Aerial Bombs at `B4`
- Rocket `F6 -> D4`, Rocket Artillery at `D7`
- Pulse `G5 -> E5`, Repulse at `E5`

Outcome: predicted dirty line matched the strategic damage: grid fell from 6/7 to 4/7, one pylon was destroyed, and bomb survived. The board presented four meaningful threats (`C7`, `B2`, `C4`, `E2`) with only three squad actions.

What could have been better: no cleaner line showed up from the available solve data. The better lesson is upstream from turn 1 and run setup: avoid entering turn 2 with two-plus mechs forced off danger while also solving four pylon/building threats.

### Turn 3

Plan played:

- Jet `B4 -> A3`, repair
- Rocket `D4 -> F3`, Rocket Artillery at `B3`
- Pulse `E5 -> E1`, Repulse at `E1`

Outcome: clean stabilization. Grid stayed 4/7, the bomb survived, and all mechs remained alive.

What could have been better: this turn was the proof that the core simulator line was sound. The post-enemy enemy-count projection was optimistic, but the irreversible-value prediction was correct. Keep enemy-count/requeue projection diagnostic unless it starts affecting next-turn search quality.

### Turn 4

Initial safety block surfaced a worse dirty class first:

- Jet `A3 -> A6`, Aerial Bombs at `A4`
- Pulse `E1 -> E3`
- Rocket `G3 -> F2`, Rocket Artillery at `F4`

Deep top-K review found no grid-positive candidate. The best strategic resist line was rank 493:

- Jet `A3 -> A6`, Aerial Bombs at `A4`
- Rocket `F3 -> F1`, Rocket Artillery at `F1`
- Pulse `E1 -> D5`, Repulse at `D5`

Prediction: grid `4 -> 0`, bomb alive at `D6`, all mechs alive, two pylons/buildings lost instead of three. Live result: Victory screen reached, so this was a final-turn grid-defense/final-timing Hail Mary rather than a deterministic clean line.

What could have been better: `solve` had the dirty frontier, but `auto_turn` did not preserve enough of it in the `SAFETY_BLOCKED` payload. That hid rank 493 until manual investigation.

## Fixes Fed Back

- `src/loop/commands.py`: `auto_turn` safety blocks now carry `candidate_count`, `selected_candidate_rank`, `selected_candidate_source`, `dirty_frontier`, `lookahead_frontier`, `robust_frontier`, and `safety_widening`.
- `src/loop/commands.py`: dirty-consent IDs now use the selected candidate rank from the solve record. This prevents token drift when a requested or widened candidate is reviewed.
- `src/solver/plan_safety.py`: safety summaries now preserve `turn` and `total_turns`, letting policy distinguish ordinary timeline collapse from last-turn final-cave resist gambles.
- `src/solver/plan_safety.py`: final-cave resist gambles are allowed only as exact-token dirty consent on `Mission_Final_Cave` turn `total_turns`, with the Renfield Bomb alive, all mechs alive, no mech HP/status/danger debt, and only grid/pylon/building losses predicted.

## Followups

- Add a soft scoring/beam feature for "multiple mechs end on next-turn lethal danger" during `Mission_Final_Cave`, weighted higher when grid is low or the bomb is active.
- Keep the 3-island readiness rule live for future Hard Rusting Hulks runs: 6/7 grid with base-ish Jet/Rocket/Pulse is not enough by itself.
- If next-turn enemy projection starts selecting poor dirty frontiers, separate enemy-count/requeue accuracy work from irreversible-value safety work so clean grid/bomb predictions remain trusted.
