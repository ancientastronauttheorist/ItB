# Ordinary input acquisition: guard cost experiment

October 4, 2026. Windows build **13725832**, simulator **413**, source baseline
`31a74b4f` on `main`. The [normalized receipt](../data/solver_first/s1_ordinary_inputs_guard_cost_20261004.json)
retains one failed fresh offline original-validation world. S1 and all seven
acceptance gates remain open. No live game operation or Rust change occurred.

## Solver-facing question and outcome

The scenario remains stock PunchMech movement from visual **H8 to G8**.
Genuine actor construction needs ordinary inputs before equipment, placement,
activation and guarded Move consumption can be checked. The previous
[prefix deadline](solver_first_ordinary_inputs_prefix_limit.md) stopped before
those inputs. This tranche tested whether an equivalent managed-heap guard
could clear that cost blocker under the same budgets and full initialization.

It did not. **259 of 260** dependent roots returned with correct stacks and no
recorded failure. The fifth prerequisite palette producer again did not return;
the ordinary continuation never began. No supported tactical behavior was added.
The failed hypothesis and bounded guard evidence are retained separately.

## Candidate and synthetic evidence

Runtime06 changes only the managed-heap memory callback. An in-bounds DWORD
read uses one allocation lookup and no EIP read, compared with two lookups and
one EIP read previously. Requested extent, liveness, Lua padding and malformed
frame exception precedence remain guarded. The admitted metadata domain is the
valid monotonic allocator; corrupt, overlapping or unsorted owners are excluded.

Two synthetic checkers pass **22,848** differential comparisons; **17,968**
also use an independent interval/owner oracle. They cover adjacent owners,
gaps, liveness subsets, cross-owner spans and old-reallocation/new storage
metadata. These are synthetic states, not native allocator or gameplay cases.
The first checker's outcome digest covers 15,168 cases; 48 delegation and 32
empty-owner checks are asserted separately. The supplement digest covers 7,600.

Five alternating direct-callback samples, with 200,000 callbacks per sample,
give median old/new ratios of about **8.18 for reads** and **1.15 for writes**.
These samples use the actual Unicorn register API but execute no original
instructions or graphics. They establish no native, planner or held-out
speedup. The native acquisition still failed.

The complete 305-root prefix remains required in this launch. A source-plausible
82-root ordinary-only alternative was not executed: scratch mappings and later
initialization/ownership order remain unproven. No instruction, wall or heap
budget was increased.

## Actual original execution and exclusions

The world retains **25,080,702 instruction visits**. Its last `0x000c0ac0`
root records **7,886,011** visits against a 20-million cap, and
**200.1059226 seconds** against a 200-second wall limit. It retains
`returned=false`, `stack_ok=false`, `failure=null`; the enclosing world is
failed. Wall-limit exhaustion is inferred from elapsed time and the sub-limit
instruction count. No native timeout-query flag was retained.

The last trace position is **`0x000c0908`**, in original helper `0x000bf350`
reached through `0x000c0910` during palette CPU processing after PNG decoding.
It differs from the earlier world's final position. There is no final upload
or completed fifth palette result. Four earlier palette asset rows passed
their existing grades; two registered resources remain separate prefix
observations. None is a new ordinary-resource admission.

The first **259** completed roots match the preceding world across arguments,
returns, stacks, instruction counts/trace digests, imports and allocator
callback digests, totaling **17,194,691** visits. This is agreement over one
dependent captured prefix. The truncated final roots differ; this is neither
complete-world equivalence nor a controlled native speed/slowdown comparison.

Both pattern constructors and ctype-facet grades, the absent-global control,
78 asset predicates, nine predicate-control queries, 26 ordinary loaders and
two missing-resource queries remain unexecuted and counted as excluded.
The source-pinned 512-byte ctype service remains unexecuted; inherited 868-byte
PTD allocation and the balanced 13-lock CRT state remain acquired.
Factory, positive actor, complete action/turn, fair-input, held-out, search,
ledger and gate admissions remain **zero**.

Host graphics cleanup succeeded without errors, with no tracked texture names
remaining and the context, DC and window released. All **159** saved/current
source identities, runtime/game inputs and **13** protected user files match.
Prior 54-, 122- and 143-source acquisitions and the withdrawn 131-source
preflight remain intact. No old world was resumed or second acquisition run.

## Stop and reprioritization

Stop this acquisition. Review validation instrumentation cost and minimum
initialization needs against the named actor/action blocker before another
acquisition or helper expansion; do not automatically retry or raise budgets.
The supplied monotonic 16 MiB heap, normal-success Win32/FLS services, sliced
startup inputs and isolated host graphics remain explicit oracle boundaries.

A conditional source plan identifies equipped constructor `0x00244df0` as
calling factory `0x00245070` itself; invoking both would create two actors.
Extra stock Skill inputs, fresh global-vector ownership, placement, Board
membership, IsMech and confirmation producers remain unclosed. The plan has
no execution or readiness admission. The next exit remains genuine same-actor
ownership, guarded Move consumption, repeated-Move rejection and retained Use
eligibility, then an actual next decision and full turn.

Search was not evaluated; valid bounds are absent. No held-out strength or
latency/memory comparison was run. See the
[actor eligibility frontier](solver_first_move_actor_eligibility.md).
