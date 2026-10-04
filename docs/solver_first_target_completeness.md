# Complete base target areas and conditional search reduction

Simulator v413 separates base Tank's selectable target area from its four search
direction representatives. Both primitive admission and diagnostic attack
validation now accept every in-bounds cardinal point through the first blocker,
including that blocker. Points beyond it, diagonals and the origin are rejected.
Base Punch keeps its range-one area. Other weapon families retain their existing
filtered target contract and need separate complete-area evidence.

The original getter exposed a real v412 rejection on the pinned two-actor
fixture: Tank at E5 had 11 native target points, but the APIs admitted only four
adjacent directions. Legal clicks E7 and E8 were rejected; E3, beyond the Firefly
at E4, was correctly rejected. The original getter ran with the literal
`INT_MAX=2147483647` registration, rather than a range-eight approximation.

A second original query isolated persistent corpse occupancy. With supplied
HP0, IsMech1 and lifecycle0 bytes at E7, native `Board:IsBlocked(PATH_PROJECTILE)`
returns true, and the target ray ends at that corpse. Shipped `GetProjectileEnd`
advances until that predicate returns true. The old Tank simulation passed
through the wreck and reduced the enemy behind it from HP3 to HP2. The new base
nonphase Tank endpoint uses the existing Board path-corpse predicate and stops
at the wreck. Damage/push machinery is retained. This fixes that source-grounded
endpoint discrepancy, not all projectile families or original corpse effects.

Both minimized checks were executed against the old installed v412 build and
failed, then passed against the rebuilt v413 extension. The original queries
used the pinned Windows build 13725832, executable SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The supplied world uses source-backed Board/Tile storage, original vtables,
original validity/occupancy callbacks and original direction initialization.
The established heap seams supply declared successful responses. Original
constructors, Lua dispatch and actual death/removal continuity are unacquired.

Native member `GetSimpleReachable` is RVA `0x174060`, 137 bytes, SHA256
`59259634c2a99a3bb9b3219c3d824488130abbf2d5a4ff7126ad8c7c26e8282a`;
its core is RVA `0xcfa40`, 1,091 atlas bytes, SHA256
`6e05f5d87e1f9cf5ac16eee5a9b249bf7e1e979d7e30ac35d9612c2fc4705689`.
The ABI is ECX Board plus output-vector pointer, x, y, range and corners, with
RET20. Original corpse classification at `0x22cde0` depends on mech/sourceCorpse
and lifecycle state, with mutation alternatives outside this fixture domain.
The source registration audit pins `INT_MAX`, Rubble2 and Hole9. The normalized
query reports keep runtime/body/content identities and measured exclusions.

The [full-click reference](../scripts/solver_first_target_completeness.py)
retains every legal Tank point rather than assuming same-direction equivalence.
Python independently classifies all 64 coordinates at each reachable ready-actor
prefix, checks both legal acceptance and illegal rejection, and enumerates all
Move/Use/Repair/Wait actor orders. It includes pushed positions, deaths and
destroyed buildings becoming Rubble. Unexpected actor or terrain changes fail
closed. The baseline fixture is verified against its frozen v411 receipt before
evaluation.

At each prefix, full clicks in one direction must agree on the whole typed model
Board, ordered action results, admissions, readiness and accumulated objective
counters. Replay exposes every ActionResult field and PlanTotals. The complete
Board Debug representation is opt-in inspection data, local to the pinned build;
it is not a portable state format or planner input. Terminal outcomes, score and
clean-policy selection are compared through the complete schedule pools.
Production continues to generate four direction representatives and report
`best_found`, null certificate and null valid bounds. A successful reduction
check is conditional on this exact shared transition model and fixture.

The original query acquisition runs in a separate process consuming the
reference's unique geometry requests. HP sign normalization is explicitly used
only for `IsDead` queries. CommonPawn, sourceCorpse, lifecycle0 and empty available
mutation storage are supplied premises. These queries validate complete target
vectors in that supplied domain; model-derived query states are development
evidence, not an independently acquired gameplay differential corpus. No actual
death transition, original action outcome, fair-input admission, held-out family
or full tactical loop follows from them.

The frozen [model reference](../data/solver_first/s2_full_target_413.json), SHA256
`abac30883cb101f82265fd88ed0f33eec2f533bf3c68e2a65174d316da098e64`,
finishes all 8,120 prefixes and 7,200 complete full-click schedules with zero
projection failures or deadline cutoffs. At 951 ready-actor prefixes it checks
60,864 coordinates: 5,894 legal acceptances and 54,970 illegal rejections. Its
2,210 complete-projection comparisons establish same-direction model equivalence
for every reached target group. The reduced reference visits 3,682 prefixes and
3,121 complete schedules; full-click compound actions visit 3,384 prefixes and
2,983 schedules. These pools are exhaustive for the fixture's declared model,
not for original-game transitions or other mission objectives.

The separate [original-query report](../data/solver_first/s2_full_target_original_413.json),
SHA256 `6d9fca563b75e1d6aa6f33cd8dc7037799b21df554c0045567b96b3f1a7ce9b5`,
records **65 attempted, 65 admitted, 65 matched, zero failed and zero excluded**
geometry queries. Each has its own original execution and retained private
trace identity. Both reports preserve source/build/runtime/input pins. The
model report's query-acquisition field records its state when generated; the
separate completed report supplies the subsequent execution evidence.

Production selects the same raw/clean/policy optimum, 70,420, with zero regret
and membership in the full schedule pool. It visits 3,682 nodes and 3,121
terminal plans, with no rejected steps or cutoffs. Its 0.0518116-second result
uses a declared ten-second budget; the references each use 600 seconds. The
compound optimum remains 62,219.142903906955, a gap of 8,200.857096093045.
Production still reports `best_found`, null certificate and null valid bounds.
This single development timing provides no held-out latency or peak-memory
comparison. Neither the complete target vectors nor fixture reduction certify
the production solver's broader supported domain.

Both simulator version pins are 413. The v412 tracked failure-database baseline
is archived separately with SHA256
`a5bf0a9b459e754a3bf9c49b5564c745687273aa04fafddd60e82d9de43f0b66`.
The active failure database's user changes are preserved and unpublished.
The provisional objective remains the shared existing terminal score and clean
selection policy for one player turn, no additional spawns or hidden RNG input.
All seven goal gates remain open. Full-turn original continuity and held-out
practical baseline/candidate outcome, latency and memory evaluation remain
required beyond this tranche.

The [minimized regression manifest](../data/solver_first/s2_target_regressions_413.json)
retains the normalized old-red/current-green facts and private evidence hashes.
The [final validation manifest](../data/solver_first/s2_target_validation_413.json),
SHA256 `34a71c977795b00ee2fa9d6027ee31a1bf735468c8d996c67f501616f38191d8`,
pins the installed v413 extension SHA256
`f3dfe1c3cb1aacea28abe654419c76ca7c1353afc998e4087c3b6ec86483c674`
and 32 source files, configuration and corpus inventories. All 1,043 Rust unit
tests and six integration checks over 1,052 tracked boards pass; integration
time is 507.66 seconds. Aggregate per-case counters were captured by the Rust
test runner and are not inferred here. Focused Python validation passes 60
checks with one opt-in skip. The full Python replay passes in 81.52 seconds:
339 records, 60 fixed classifications, one known issue, 132 missing boards,
146 empty solutions, 61 action-required cases, zero required-empty cases and
zero unexpected regressions. These are sanity/self-consistency classifications,
not game victories or original transition comparisons.

Three additional diagnostic far-click calls admit all requested points and
agree on final board and action results. Their whole reports differ only at
`predicted_states/0/post_attack/tiles_changed`: diagnostic replay explicitly
samples the clicked target and its surrounding 3x3 tiles, including unchanged
tiles. Two prepublication checks rejected whole diagnostic-report equality;
the manifest retains that reporting limit and the private comparison receipt.
No sparse diagnostic field is dropped from the complete primitive proof above,
which separately compares the whole typed model Board.

Continue: this tranche reproduces two v412 defects, repairs base Tank admission
and corpse endpoints, and closes the fixture's previously assumed target
reduction with explicit full-click comparison. The next S1 exit test remains an
original admitted action, ordered immediate effects and enemy/environment/spawn
continuation into the next decision state. Original action effects, corpse
lifecycle and observation legality take priority over extending helper counts.

Run model comparison, then original acquisition, serially:

```text
python scripts/solver_first_target_completeness.py --output <new-model-report.json> --reference-budget 600
python scripts/solver_first_target_area_oracle.py --executable <pinned-Breach.exe> --reference-report <new-model-report.json> --runtime-path <pinned-emulator-package> --output <new-original-query-report.json> --private-output-dir <new-private-directory>
```
