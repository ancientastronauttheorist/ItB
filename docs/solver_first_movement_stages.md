# S1 coordinate and arrival stages

This checkpoint extends the [path-query evidence](solver_first_path_query_conformance.md)
to original coordinate writes and tile membership relocation. Three legal
constructed movement compositions agree with Rust v409 on the moving pawn's
final position and unchanged 3 HP. Original membership vectors contain the pawn
on exactly its coordinate tile after every stage. This is a native conservation
check; Rust does not expose the same pointer-vector representation.

The primary grounded Massive route probe still fails before its first move at
the original `lua_pushvalue` import. The successful stage compositions do not
replace that failed acquisition or prove complete movement execution. S1 and
all seven [acceptance gates](SOLVER_FIRST_PLAN.md) remain open.

## Tranche progress report

| Required dimension | Checkpoint |
| --- | --- |
| Build / solver / corpus / information / objective | Windows build13725832; solver baseline `d26e94519fb15b14d1692a26169c9ffac8596b28`, v409; `s1-coordinate-arrival-development-v1`; provisional player observation v1, offline only; fidelity comparison, no planner objective change |
| Named blocker and reachable scenario | Does Massive H8→G8→F8 through Water preserve the coordinate/membership/HP projection? Does the original route pump deliver it? |
| Before → after supported behavior | Query-only evidence → executed coordinate/arrival stages; full route remains unacquired |
| Original evidence and supplied boundaries | Guarded original x86 bodies in a reconstructed sparse world; supplied pilot/definition state and heap responses; no complete game process |
| Differential attempted / admitted / passed / failed / excluded | Stage recipes 4/4/4/0/0 for declared fields, including one illegal control; full-route entry 1/0/0/1/1 at known Lua boundary; complete turns 0; archived observation families 1, pinned-build admissions 0 |
| Search status and bounds | No search evaluation or certificate; no new valid bound |
| Held-out outcome / latency / memory | No held-out evaluation or baseline/candidate performance comparison |
| New uncertainty / regressions / exclusions | Speed lookup is configuration, and Ground-origin animation needs Lua; no new Rust change or reproduced semantic mismatch; ordered effects/readiness/full updates remain excluded |
| Next milestone and work selection | Acquire a provenance-complete original movement/effect transition or close the exact Lua boundary. Reprioritize toward that acquisition before further helper audits; the new stage projection removes uncertainty, but repeated entry-pump failure alone would not justify another tranche. |

## Executed stages and denominators

The [runner](../scripts/solver_first_movement_stages.py) reuses the pinned x86
query machine and its guarded original instructions, successful heap seams,
actual-return checks, and frozen executable/atlas identities. The
[report](../data/solver_first/s1_movement_stage_report.json) records:

| Subsystem | Attempted | Result |
| --- | ---: | --- |
| Declared query/projection recipes | 4 | Four completed, zero unexplained mismatches |
| Query-admitted stage compositions | 3 | Four coordinate-writer returns and three final-arrival returns |
| Ground-to-Water illegal control | 1 | Native GetReachable and Rust reject; no coordinate/arrival call |
| Grounded Massive pending-two-point entry pump | 1 | Zero admitted returns, one retained failure at the declared Lua boundary |
| Full original movement/turn transitions | 0 | Unverified |

The legal recipes are Massive H8→G8 Water, Massive H8→G8→F8 through Water,
and Ground H8→G8 with G8 changed to Ground. GetReachable supplies the native
destination predicate. Coordinate writer `0x230320`, receiving ECX=Pawn and
two stack coordinates with RET8, invokes `0x2301b0` and Board relocation
`0x162060`. Final arrival `0x162140`, receiving ECX=Board with the same RET8
coordinate ABI, invokes the tile resolver `0x19d4b0`.

The two-step composition manually calls both coordinate writers and then the
final arrival. It does not execute the route timer, intervening Board/Pawn
updates, or intermediate tile-frame callbacks. HP agreement establishes
preservation in the clean fixture; no damage/status rule is admitted from it.
Only position and HP are compared with Rust. Action consumption/readiness,
ordered events, settled statuses, and full-turn state are explicitly ungraded.

## Supplied world and closed child dependencies

The executable is Windows build13725832, SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The world extends the query fixture with declared zeroed Pawn/definition/pilot
storage. Pawn+944 names Board; +874 names the supplied definition; +1168 is
INT_MAX for idle; +99d is the recipe's Massive flag. Fire/Frozen/ACID, the Pawn
Flying flag, additional-tile vectors, and the base/render-grid pointer are zero.
This is a detached base-object domain, not proof of spawned-pawn attachment.

The embedded busy object is actually constructed by original `0x15dfb0` at
Pawn+a74. Its original vtable VA82e11c and virtual+4 predicate `0x15c4d0`
support the native idle check `0x22cce0`. Busy flags are not set to bypass it.

Native IsFlying `0x23e490` first selects a pilot pair through `0x23e3b0`, then
checks the pilot ability through `0x220a30`. Empty Pawn+94 storage alone cannot
establish grounded movement. The fixture supplies a source-compatible empty
pilot ability record Q=C+12, genuine control/object vtables82b804/835dcc,
strong/weak counts1/1, empty inline Skill length0/cap15, zero extra abilities
and power gate, and the owner pair at Pawn+a6c/a70. The original getter,
comparison, shared-pointer copy, and release execute; the result is false and
the counts remain1/1. Full Pilot_Artificial/Pawn-definition loading is excluded.

The [static boundary](../data/solver_first/s1_movement_stage_static_boundary.json)
pins these source facts. Its constructor-derived empty record is a supplied
premise, not an executed complete pilot constructor or a Lua-loading receipt.
The report pins the implementing runner, acquisition dependencies, runtime
libraries, loaded Rust extension, and observation contract. Raw traces remain
private. Simulator semantics and version409 are unchanged in this checkpoint.

## Retained full-route failure

The original route pump `0x233110` reads `speed` through `0xd3e30`; this is an
integer configuration lookup, not an RNG-duration helper. Original initializer
`0x3100` requests11 and selects17 from the pinned prime table. A supplied fresh
map has bucket count17, size0, load factor1.0, threshold0 and null bucket array.
The original lookup/insertion computes default500 and allocates its node and
buckets through the admitted heap seam.

The grounded step then calls `0x174390`, a tile-animation wrapper, rather than
the previously presumed sound wrapper. It reaches tile `0x1ae630`, animation
constructor `0xbb910`, and Lua-backed configuration `0x4e800`. Original helper
`0x6c3e0` calls `lua_pushvalue` at `0x6c3ec`, IAT3d64e4. No Lua response is
supplied. The recorded fault retains its partial trace/import identity and H8
coordinate/membership. An unexpected failure at another seam makes the CLI fail.
CLI success here means the stage comparisons succeeded and the known unsupported
route boundary was reproduced; it does not mean full movement passed.

Sound `0xdb070` has a separate audio-disabled entry branch. Active FMOD and
animation/resource/Lua setup remain unresolved. An eventual entry-pump return
alone would still require route exhaustion, timer completion, Board updates,
and settled effects before claiming a completed original movement.

## Archived game evidence and next exit test

The [archive audit](../data/solver_first/s1_archived_movement_projection.json)
pins seven retained sources for BomblingMech E6→D5. Actual bridge input and a
linked post-move board snapshot confirm its position change and 3 HP, joined
through the append-only action log and move verification. The latest solve was
overwritten by a partial re-solve and is not the original action list.

That family lacks executable identity, an independent command ACK, and actual
post-move status/readiness fields. Another actor and dam flooding occurred
between the start-of-turn input and after snapshot. It supplies one limited
archived observation family, zero transitions admitted to the pinned Windows
corpus, and no isolated Water/Smoke/Fire or complete-turn equivalence.

Next, acquire a complete movement/effect before/action/after family with build,
delivery and status provenance, or close the original animation/Lua boundary
without replacing gameplay results. Then join route/tile updates and
enemy/environment resolution into the next decision state. There is no
held-out evaluation, search certificate, practical promotion, or ledger
promotion from this checkpoint.
