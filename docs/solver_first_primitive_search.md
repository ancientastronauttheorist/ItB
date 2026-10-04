# Offline primitive action search, simulator v412

This tranche extends the [solver-first contract](SOLVER_FIRST_PLAN.md) with an
offline atomic planner and one independently enumerated synthetic armed fixture.
It does not complete S1, S2, or any of the seven acceptance gates. The published
baseline is `fddd16c8de4c9232ec29366402c2cc38016aa58c`, simulator v411.

## Reachable blocker and before/after behavior

The legacy planner schedules one compound move/use operation per actor. An armed
actor can instead move out of another actor's way, let that actor move and push an
enemy, then use its own weapon. Permuting compound actor orders cannot express
that schedule. A repeated-UID legacy diagnostic happens to project it, but does
not spend movement readiness correctly; it is not a sound primitive planner.

The [v411 counterexample](../data/solver_first/s2_primitive_411_counterexample.json)
freezes a two-mech corridor with two buildings and one Firefly. Tank
starts at E5, Punch at E8, Firefly at E4, and buildings at E2 and F4. All coordinate
names here use the bridge-to-visual conversion, not ordinary Cartesian labels.
The winning sequence is Tank Move to D3, Punch Move to E5, Punch Use at E4, then
Tank Use at E3. Both buildings survive and the Firefly dies. Its shared-model
score is 70,420; the old compound solver selected 62,219.142903906955. These are
provisional scalar objective values, not original-game outcomes or win rates.

`itb_solver.solve_primitives(input_json, budget_seconds)` now searches atomic
`Move`, `Use`, and `Wait` choices across eligible actors. Its output uses `steps`,
with `kind`, `mech_uid`, and kind-specific fields. This is an offline format and
has no adapter to live bridge execution. Legacy `solve`/`auto_turn` still use the
compound format and schedule.

`replay_primitives(input_json, steps_json)` validates a prefix on a cloned state,
returns the post-player board and an explicit per-UID entitlement ledger, and
scores enemy/environment/spawn projection only after all currently eligible
actors have closed their actions. A rejected step leaves the supplied prefix
unchanged. Move spends movement while preserving Use; Use and Wait close both
ordinary entitlements. Use/Wait call attack-only transitions and shared player
finalization, without repeating movement/landing pickups. Move still delegates
to the existing movement simulator. Extra movement/use grants remain unsupported.

Callbacks can admit fresh active controllable actors, including armed non-mechs.
An actual synthetic Hacking facility-destruction test verifies that fresh bot
UID42 enters the action ledger and prevents premature completion. It verifies
the Rust callback integration, not original callback timing. Repeated UIDs do
not receive fresh entitlements; dead actors cannot act, and pushes preserve an
untouched actor's ordinary entitlements.

The compound and primitive search share the extracted terminal objective,
including event bonuses, enemy/spawn projection, and the existing clean-plan
selection threshold: prefer a clean candidate within max(5% of absolute raw
score, 500 points). The old diagnostic `score_plan` formula remains a separate
historical implementation; this tranche does not claim general parity for it.

## Native targeting dependency

The reference retains building-bound Tank and Punch shots. Their existing Rust
target filters rejected such directions, preventing complete traversal. The
[normalized native receipt](../data/solver_first/s2_primitive_target_membership_412.json)
records the retained Windows build and guarded original `GetSimpleReachable`
query, wrapper RVA `0x00174060`, core RVA `0x000cfa40`. The member ABI is ECX Board
plus output vector, x, y, range, and corners; the wrapper returns with RET20.
The original query includes a valid first blocker endpoint.

Acquisition accounting is one pre-native environment rejection (missing module
on the default import path), then three admitted original queries: empty-ground
adjacent control, four adjacent blockers at range1, and the same blockers at
range8. All three returned the four expected adjacent points, with zero
membership mismatches or provenance failures. Runtime/binding/body/source hashes
are pinned before and after. Original instructions, allocation/copy/free bodies,
Board validity/traversal callbacks, and original direction initialization execute;
the established heap import seams supply only their declared successful boundary.

The world is supplied zero-filled Board/Tile/pawn storage with source-backed
offsets, an 8x8 extent, Ground terrain, and Building1, Mountain4, friendly and
enemy pawn blockers. No original constructors, Lua dispatch, full-game action,
or HP of the Building-terrain fixture is acquired. The projectile traversal
branch does not consult building HP. Range8 is board-bounded equivalent for the
center cardinal scan, not the literal INT_MAX Tank Lua argument. The recorded
body list includes preverified bodies and does not claim every listed body ran.
No function ledger entry is promoted.

Shipped base Punch inherits the Skill range1 getter; base nonphase Tank inherits
TankDefault's getter. Those two Rust IDs now retain all in-bounds adjacent
directions, including building-bound shots. The regression fails against the
prior filter (empty targets versus four) and passes with the correction. Tank
still uses adjacent direction representatives rather than every native selectable
point along a ray. The fixture comparison is over those representatives; a full
legal-click-set fidelity claim and the reduction's general equivalence remain
open. Upgrades, Split Shot, other melee/projectile families, and overridden
getters retain existing behavior pending their own evidence.

## Independent reference and limits

[The reference](../scripts/solver_first_primitive_search.py) accepts only the
exact pinned normalized fixture. Python supplies Ground/Rubble BFS, friendly
live transit without occupied stops, enemy/dead-mech blocking, every in-bounds
base weapon direction, full-HP Repair, Wait, and every atomic actor order. It
also enumerates a contiguous compound schedule pool for comparison. Initial
Building tiles may become Rubble; unexpected terrain or actors fail closed.

Readiness is derived independently from the typed Python prefix, then checked
against Rust's ledger and board flags. Both player UIDs must remain in projected
boards, including dead persistent wrecks; actor identity, HP, and coordinates
are checked. Python independently classifies clean plans from surviving building
count and player damage receipts. Returned error events and malformed receipts
are rejected. Meaningful mock mutations cover mutually consistent wrong Rust
readiness, disappearance of an actor, nonlethal building damage mislabeled clean,
and returned illegal-action events.

Rust alone projects combat effects and computes the scalar terminal objective.
Python does not introduce a second combat simulator. Thus independent schedule
enumeration and classification are conditional on the shared Rust transitions
and scalar scoring. Any projection rejection stops that reference and retains
partial counts; it is never silently dropped to manufacture exhaustion.

The fixture is development-only synthetic evidence, with no held-out family or
fair archived-game admission. No pilot, upgrade, secondary weapon, disabled
weapon, paired target, mission ally, environment, spawn, RNG, or longer horizon
enters this exact comparison. The Rust atomic API's broader unvalidated model
surface must not be mistaken for a certified supported domain. Paired weapons
reuse the existing filtered generator; disabled weapons are hard-excluded,
without the legacy forced-use fallback. No state-transposition reduction is
used because event history affects the objective.

Production reports `best_found`, a declared budget and elapsed time, generated
steps, visited nodes, terminal plans, rejection reasons, deadline/depth cutoffs,
and whether its generated tree was exhausted. Certificate and valid bounds are
null. That exhaustion describes the current model candidate generator; it does
not establish original legality, a complete native target set, or campaign
optimality. Depth is capped at 64; cutoffs remain explicit. Budget0 returns no
fake score or fabricated terminal plan.

## Configuration, validation, and continuation

Simulator v413 follow-up: [complete base target areas](solver_first_target_completeness.md)
repairs far-click admission and persistent-corpse Tank endpoints, then compares
the four direction representatives with a complete 7,200-schedule full-click
reference. All 65 supplied-world original target queries match. The v412
reports and build identities below remain historical. Full original action
effects, state continuity and general search certificates remain open.

October 3 follow-up: the [Python corpus admission repair](solver_first_regression_admission.md)
adds a read-only inspection API in a distinct v412 extension build and repairs
the required-empty guard. The extension identity and Python corpus counts below
describe this primitive tranche's historical build. Its frozen reports remain
unchanged; the follow-up supplies its own source/build/corpus pins.

The normalized fixture uses default Rust weapons/evaluation, grid7, one player
turn, no additional spawns, no environment, and no hidden RNG input. Rust retains
its default 15% expected grid-save credit; unknown JSON `grid_defense` fields are
not used to imply zero resistance. Caller information admission remains separate
from this model experiment. Source, loaded extension, baseline receipt, and
fixture hashes are frozen in the generated comparison report.

Both simulator pins are 412. The tracked v411 failure corpus is archived as
[failure_db_snapshot_sim_v411.jsonl](../recordings/failure_db_snapshot_sim_v411.jsonl),
SHA256 `a5bf0a9b459e754a3bf9c49b5564c745687273aa04fafddd60e82d9de43f0b66`.
Existing user edits to the active failure database and twelve other protected
paths are preserved and excluded from this publication.

The [frozen comparison](../data/solver_first/s2_primitive_412.json) admits all 3,682
atomic prefixes and scores 3,121 complete schedules, versus 1,516 prefixes and 1,286
complete compound schedules. Both references finish without projection failures
or cutoffs. Production visits the same 3,682 nodes and 3,121 terminal plans, with
zero rejected steps and no deadline/depth cutoff. Its selected sequence belongs
to the independent pool, scores 70,420 in both paths, and has zero raw/policy
regret. The compound optimum remains 62,219.142903906955, a gap of 8,200.857096093045.
Production reports `best_found`, null certificate/bounds, and 0.0463263 seconds
within the declared 10-second budget. This is one development fixture's timing,
not a held-out latency distribution or speed comparison.

The earlier [rejected reference receipt](../data/solver_first/s2_primitive_412_rejected_sparse_projection.json)
retains two root rejections caused by the reference expecting a dense tile list.
Rust legitimately omits wholly default Ground. Python now fills only missing
originally Ground coordinates; omitted Chasm/Building/Rubble fails closed.
The receipt is not an original-game/model mismatch or a successful enumeration.

Final Rust unit validation passes 1,043 tests, including the old-red/new-green
building-target regression. The installed v412 release extension SHA256 is
`a889535d9353fe125dd98d3c1adbafbbfddc5f765fe1b09e7e289b07d09ed19e`.
Python validation passes 67 retained tranche checks plus all 28 focused reference
checks after the sparse-representation correction. One opt-in native test is
skipped. The separate create-only native comparison
above supplies actual integration evidence. All six Rust integration regression
checks pass over 1,052 tracked boards (303 require actions), with zero unexpected
failures. That harness checks crash/empty-action/bounds behavior, not original
transition fidelity or exact score equality. The Python failure-database replay
also passes: 339 filtered records, 60 classified fixed, one known issue, 132
missing recorded boards, 146 empty solutions, and zero unexpected regressions.
Those are the harness's classifications; missing/empty cases are not successful
original-failure reproductions. Neither regression harness closes the independent
original differential or held-out evaluation gates. Reproduce
the create-only comparison with:

```text
python scripts/solver_first_primitive_search.py --expected-simulator-version 412 --output <new-report.json>
```

Continue: this tranche reproduces a missing armed schedule, closes a named native
query dependency, and adds explicit readiness accounting. Practical held-out
outcomes, latency distributions, and peak-memory comparisons remain unmeasured;
there is no promotion claim. All seven goal gates remain open. The next S1
milestone is still an original selected action, its ordered immediate outcome,
and enemy/environment/spawn continuation under admitted information. The next
S2 increment must independently compare a broader declared action domain and
establish target-representative equivalence before claiming a certificate.
