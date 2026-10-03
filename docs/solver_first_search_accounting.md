# Search accounting and bounded independent comparison

This tranche addresses the search gate independently of the open original-game
tactical-loop gate. Production Rust JSON now explicitly reports `best_found`,
one player-turn horizon, null certificate and null valid bounds. Beam chains
also report `best_found` and their requested horizon. No optimality claim is
inferred from timeout flags or actor-order counts.

## Production accounting

Each parallel actor-order invocation owns counters, reduced in input order.
`nodes_visited` counts recursive entries admitted by the existing deadline
guard; `terminal_plans_evaluated` counts fully scored leaves. Generated action
counts precede action-cap pruning; pruned candidates and encountered disabled
action skips have separate counters. Deadline cutoffs count encountered aborts,
not the unknown number of omitted branches. No clock checks, ordering, scoring,
pruning policy or transition semantics were added or changed.

Scheduled, started and completed **order passes** are distinct. A pass completes
only if its root started and no descendant encountered a deadline cutoff.
The optional disabled-weapon fallback contributes another pass to these totals.
Legacy `permutations_tried` counts unique actor orders actually started across
passes, rather than reporting every scheduled order as tried.

`retained_candidate_tree_exhausted` means every scheduled order pass finished
without a deadline cutoff. It may be true after heuristic action-cap pruning
or generator filtering. It is not legal-action completeness, model fidelity,
objective certification or campaign optimality. The single-best planner also
has a player-caused building preservation post-filter; its selected score need
not be the raw maximum on arbitrary weapon-bearing boards.

Top-K retained solutions each carry the same whole-search audit. Consumers must
not sum those copies. Beam level-zero copies likewise represent one invocation;
each distinct projected level-one solve has its own audit. Empty top-K/beam
arrays currently omit invocation statistics, and absent projected continuations
are not exhaustive-frontier evidence. The existing minimum beam sub-budget can
overrun a requested total budget. No sound bound is available.

The added counters have runtime overhead, so deadline-limited choices may change
even though candidate order and selection policy are preserved. Complete small
searches are checked for stable plans and accounting. This tranche changes no
simulator physics and retains simulator version 410.

The legacy Python command wrapper currently discards the new metadata. Its
existing completion display is not a proof label. That integration remains
open because the shared command file contains protected pre-existing work.

## Independent reference boundary

The bounded reference independently enumerates actor orders, cardinal BFS
destinations, Wait and Repair for a declared synthetic domain of disarmed
player mechs. It includes legal full-HP Repair, which the production generator
filters. It independently enforces one compound action per actor and occupancy;
Rust accepting `score_plan` input is never treated as a legality check.

Rust `score_plan` supplies terminal transition/evaluation results. This is an
explicit shared model oracle for a **search-only** comparison, not an independent
simulator or original-game differential test. Agreement applies only to the
enumerated inputs, supplied model, one-turn horizon and frozen evaluation.
Neither synthetic construction nor a conditional exhaustive comparison promotes
the production root to `proven_optimal`.

The arena has ordinary Ground bounded by Mountains, no pilots, statuses,
passives, environmental hazards or spawns. A Firefly threatens a building;
wounded blocking mechs can survive by repairing before its shot. This creates
a decision-sensitive alternative to an empty-board movement test. Full-HP
Repair remains a separate legal choice; no terminal deduplication assumes that
Wait and Repair produce identical readiness flags.

## Work selection and remaining gates

The retained August 24 action-selection audit inspected six source families,
18 pair containers, 45 validated outcome artifacts and six ordered-effect
artifacts. It found zero complete before/action/immediate-after execution pairs.
The closest Firefly return is the next selected intent, not its execution.
Private packet SHA256:
`99105bbf9a4a3d3ba2982b6aa90a4d4f36c1cf20e439f5218619f2c8bb4d5b67`.

The ordinary May 10 turn candidate has full turn-boundary boards but lacks
individual action ACKs, a complete post-player board and build/overlay/loadout
attestation. It remains legacy development material, with zero fair or complete
original-transition admissions. Private packet SHA256:
`c72af33ceedadb1842bcb672d9eed11fa7b1db89a8b04d4ab32bc0c9b715b770`.

These exclusions led to reprioritizing the independent search requirement rather
than extending another helper chain. S1 and all seven full prospective gates
remain open. There is no held-out promotion, practical baseline comparison or
campaign claim. Scope, risk, horizon and budget choices must be resolved before
dependent practical evaluation. The next original-evidence milestone remains a
full player-action/enemy-resolution/next-decision join; search work next needs
broader legal actions, mission allies and a sound certificate policy.

## Validation

The rebuilt and installed v410 release extension is pinned by SHA256
`35ce67e3f8048f406bdb3ef4339baeb9010aca3dc8ef98b94647ac0bb65b3c9a`.
All 1,023 release Rust unit tests and 31 Python checks passed, including accounting,
independent-reference sensitivity, top-K/beam wire scope and existing solver
determinism. An initial Python test used the wrong top-K argument order; the
corrected suite passed. No simulator-version bump or failure-DB replacement is
needed for this reporting change.

The [frozen comparison](../data/solver_first/s2_bounded_search_410.json)
scores 18,180 independently enumerated legal plans across four cases. Each case
completed all actor orders with zero oracle failures, zero regret and exact
reported-score/rescore parity. Source snapshots and loaded extension bytes
remained unchanged throughout acquisition. Raw and LF-normalized source hashes
are preserved; the snapshots do not independently attest source-to-binary build
linkage. No fair/original/held-out admissions were made.

| Synthetic case | Reference scored leaves | Production scored leaves | Regret / score difference |
| --- | ---: | ---: | --- |
| One wounded actor | 16 | 16 | 0 / 0 |
| Two wounded actors | 340 | 340 | 0 / 0 |
| Three wounded actors | 8,912 | 8,912 | 0 / 0 |
| Three full-HP actors | 8,912 | 1,114 | 0 / 0 |

The full-HP difference demonstrates the reporting boundary: production filters
Repair choices before counted candidate generation, yet still exhausts its
retained tree and matches this fixture's reference value. This is four attempted,
four admitted, four passed and zero failed **synthetic search comparisons**,
with zero original-transition or held-out comparisons. It does not certify the
entire validator-admitted state space. Reference scoring took about 4.8 seconds
for each three-actor fixture; these diagnostic runtimes are not held-out latency
or strength measurements.

The four selected plans and scores also match the pre-accounting v410 extension
SHA256 `3e2229d0f36aae85f12fc97ca74232782ac971fdc0976484e1101020d06e6782`.
That is a completed-fixture invariance check, not a practical strength benchmark.
A first private comparison imported a copied older global extension because its
directory shadowed the installed package; the corrected isolated comparison
passed. Native jobs ran serially. All 13 protected pre-existing local files were
checked against their preservation hashes and remain outside this tranche.
