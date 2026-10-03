# S1 bounded original path queries and friendly transit

This tranche connects original Windows path-query output to a concrete Rust
movement defect. In the H8–G8–F8 corridor, an ordinary Massive player Pawn can
transit through a live player Pawn on G8 Water and reach F8 with budget two.
The occupied G8 tile remains an illegal stop. The v408 replay rejected F8 as
`illegal_move:0:2:out_of_range`; v409 changes both movement enumerators to use
the moving unit's team when deciding ordinary live-unit transit.

The query evidence has a constructed offline world and supplied successful
heap responses. It does not establish the complete movement transition or a
faithful tactical turn. S1 remains incomplete and all seven acceptance gates
in [the plan](SOLVER_FIRST_PLAN.md) remain open.

## Source and execution boundary

The executable is Windows build 13725832, SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The public implementation is
[solver_first_path_oracle.py](../src/observatory/solver_first_path_oracle.py),
with [its command wrapper](../scripts/solver_first_path_oracle.py) and
[the static world/ABI fixture](../data/solver_first/s1_path_query_fixture.json).
The fixture is a source/dataflow specification; its `native_execution: false`
does not serve as an execution receipt. Runtime results are separate artifacts.

The oracle executes original x86 `Board:GetReachable` at RVA `0x174180` and
`Board:GetPath` at `0x1742d0`, their original search helpers, GridSearchable
callbacks, and tile predicates. It maps pinned PE code/data, executes the
original direction initializer at `0x3030`, supplies fresh cache/world storage,
and checks each encountered instruction against a pinned original body.
Successful HeapAlloc/HeapFree responses are supplied at declared CRT seams.
Unknown imports, unsupported helper conditions, and incomplete original returns
fail closed. Original Board/Pawn constructors, definition loading, and
`GetPathProf` are not executed; no original-game DLL or process is executed.
The emulator and decoder runtime libraries are loaded and their actual hashes
are recorded. The static fixture hash identifies a reviewed reference document;
the executable world is authored by the pinned oracle implementation.

The fresh world has one live mover at H8 `(0,0)`, optional one live blocker at
G8 `(0,1)`, Ground at F8/E8, and Mountain elsewhere. Variants replace G8 Water
with Ground, change the blocker team, change budget one/two, or remove the
origin occupant. No status, item, directional wall, corpse, NonGrid/burrowed
occupant, or multiple-occupant case is admitted. World bytes are supplied
premises, not model-generated query answers. Raw body bytes, traces, local
binary locations, and identifying local paths remain private.

## Team prefix and the historical label correction

The shifted path-profile prefix is **team**, not UID. The registered seven-byte
`Pawn:GetTeam` getter at RVA `0x23d850` returns Pawn dword `+0xb0`. Its SHA256 is
`a33ed4c54f724b1cdd526b3c3e8bfc670f9881db0df0a549f9dd82f82745c8cf`.
The 34-byte registration window at `0x27c1c1`, SHA256
`ef6daf844d8d0df8bd6c920735f77996c14931c67e272b4e742ce32ea34a4de5`,
ties that body to the `GetTeam` name.

The complete 314-byte `GetPathProf` body at `0x232f90`, SHA256
`3cc91e8ef2be9950114b088f141a4087057bf7eee702aade83be716e1bccfa40`,
loads this same `+0xb0` field in every return branch, shifts it left four, and
ORs the low profile. Its ordinary Massive fallback calls `0x234e90` at
`0x2330a9`, loads team at `0x2330b5`, shifts at `0x2330be`, and ORs at
`0x2330c2`. Accordingly the supplied full player profiles are **16 Ground**
and **18 Massive**: `(1 << 4) | 0` and `(1 << 4) | 2`.

The earlier sealed path-boundary/cost-ordering receipts remain preserved. Their
"pawn identifier", UID-prefix, and no-team semantic descriptions are
superseded by this registered-field proof and the corrected fixture. Supplying
low profile 2 alone encodes prefix zero; it cannot establish equivalence with
an ordinary player `GetPathProf` result of 18. The getter/profile bodies are
verified as source identities here; their verification does not imply original
definition loading or `GetPathProf` execution.

## Query corpus and Rust projection

The development campaign defines **15 original queries**, divided as follows.
These counts describe the intended campaign denominator; the final execution
and comparison outcome is recorded separately below.

| Query group | Cases | Comparison scope |
| --- | ---: | --- |
| Occupied-origin `GetReachable` | 9 | Nine native vectors, each compared with all 63 distinct Rust destinations: **567 checks** |
| Unoccupied-origin `GetReachable` control | 1 | Original vector includes H8; no Rust mover projection |
| `GetPath` controls | 5 | Ordered route construction, independent of movement-destination legality |

The nine occupied-origin recipes cover Ground/Water rejection, Massive/Water
with budgets one/two, friendly/enemy Water blockers, friendly budget-one
rejection, and Ground with friendly/enemy/no blocker. The native occupied-origin
query excludes H8 through destination occupancy filtering. Rust intentionally
retains the current tile as a no-op option, so H8 is excluded from the 567
distinct-destination comparisons and that policy difference is explicit.

The five route controls are Ground to G8 Water, Ground beyond intermediate
Water to F8, Massive to G8, Massive through Water to F8, and same-point empty
path. `GetPath` is a route builder: after traversal rejects a neighbor, the
core can still admit it when it is the requested endpoint. Ground's route
H8/G8 therefore does **not** establish a legal Ground move or stop on Water.
Ground beyond intermediate Water remains a separate negative control.

The first v409 execution admitted all 15 original queries and compared 567
distinct Rust destinations with zero mismatches or failed/excluded recipes.
The final normalized [query report](../data/solver_first/s1_path_query_report.json)
pins the original build, frozen atlas, visited body identities, query/initializer
trace hashes, supplied world hashes, actual runtime libraries/bindings, frontend
sources, and loaded extension. Admitted native queries and completed cases have
separate counters so a later projection failure cannot inflate a passing count.

Validation: 29 focused movement tests and all 1,016 Rust unit tests passed.
Nine Python checks exercise oracle rejection and recovery: wrong build, failed
body-cache admission, incomplete instruction budget, modified code,
non-instruction entry, unknown import, wrong heap caller, freed vector,
and oversized vector capacity. Seven require the local original executable
and pinned runtime; they skip when those inputs are unavailable. The wrong-build
and body-cache checks use synthetic faults. The complete Python run passed
34 checks. Rust was rebuilt in release mode and the v409 wheel installed.
The recorded-board regression passed all **1,052** boards, including **303**
parsed boards requiring actions: zero expected or unexpected failures,
518.28 seconds. These corpus checks exercise search stability and plan
sanity; they do not compare each result with a matched original transition.

The Python suite and an initial final acquisition briefly overlapped; that
acquisition is retained privately as a diagnostic. The published report was
reacquired alone after both processes finished. Future tool calls must wait
for every running process before starting another native runtime check.

## Reproduced defect and v409 change

The normalized [v408 mismatch](../data/solver_first/s1_friendly_transit_v408_baseline.json)
preserves baseline commit
`9e5f849ac9e6f5aad04cc721c33be06e89688a6f`, simulator version 408, and loaded
extension SHA256
`33dc9aedb7a2a3a5bfdb9b412d7eed8d84a7d7b72d4592237ceb84a65c98b9c4`.
It records native full-profile-18/budget-two output F8 through a live team-one
blocker on G8 Water. Rust rejected the F8 action and left the mover at H8.
This is a minimized query-versus-replay discrepancy; it is not an original
gameplay before/action/after trace.

In [movement.rs](../rust_solver/src/movement.rs),
`reachable_tiles_with_speed` and `controlled_reachable_tiles_with_cost` now
permit ordinary transit through a different-UID live occupant with the same
team. They continue to exclude occupied destinations. Different-team live
occupants continue to block ordinary Ground/Massive transit; existing
Roadrunner and flying behavior remains inherited. The correction uses the
moving unit's team, including controlled enemy movers, rather than assuming
every controllable unit is player-team.

Rust's declared team scope is canonical IDs 1/2/6. The original query recipes
use player mover team one and blocker teams one/six; they do not provide an
original-query proof for every canonical team pairing. Unknown teams, corpse
lifecycle, NonGrid/burrowed occupants, and multiple occupants remain unresolved
for this joined conformance claim. Existing separate regressions or source
receipts do not silently enlarge the admitted query corpus.

Both simulator pins advance to 409. The tracked HEAD v408 failure database is
archived as
[failure_db_snapshot_sim_v408.jsonl](../recordings/failure_db_snapshot_sim_v408.jsonl),
SHA256 `a5bf0a9b459e754a3bf9c49b5564c745687273aa04fafddd60e82d9de43f0b66`.
The existing dirty user database was privately preserved and remains untouched;
the archive represents tracked HEAD, not that dirty working copy.

## Next movement/turn boundary

Query agreement does not execute the queued AddMove consumer. Static evidence
in [the consumer boundary](../data/solver_first/s1_movement_consumer_static_boundary.json)
connects type-four/mode-zero records to installer `0x235f00`. Its destination
route lives at Pawn `+0x8fc/+0x900/+0x904`. Exact `0x233110` is a **447-byte
route pump**, SHA256
`bbd6d10e7144c45e7f1acc79170e159f1650c489e254b72feed7854195581d36`;
the distinct `0x2332d0` status/presentation body is **3063 bytes** across two
atlas ranges. The historical larger region starting at `0x233110` must not
be treated as one function.

The adjacent step commits source/target coordinates through `0x2301b0`, with
new x/y stores at `0x2302b8/0x2302c1`, after Board tile-vector relocation.
The final-step callback reaches tile resolver `0x19d4b0`, but tile-frame update
`0x19e490` also calls that resolver at `0x19f459` before Pawn updates. Thus
intermediate route occupancy can encounter terrain/status processing; a
final-only effects claim is not proven. Timer progression, activity/busy flags,
interruption, callbacks, ownership, and completion still need joined execution.

The next exit case joins origin-inclusive N2/N3 routes to the live-Pawn update
path in the offline original world, captures intermediate coordinates and
statuses/effects, confirms route exhaustion and Board busy/completion, and
continues through enemy/environment resolution into the next decision state.
It must retain original-versus-supplied boundaries and report unsupported
branches. There is no held-out evaluation, complete-turn comparison, search
certificate, or S1 promotion from these path queries.
