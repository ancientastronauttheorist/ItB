# Player AOE source corrections and bounded search checks

Development tranche: 2026-10-03, simulator v411, following main checkpoint
`3b7f85f1d5516a69a7c14772295136f99fd1dc8d`. The full acceptance contract remains
[SOLVER_FIRST_PLAN.md](SOLVER_FIRST_PLAN.md). All seven gates remain open.
This tranche demonstrates source-shaped model corrections and a new bounded
search comparison. It does not complete S1 or certify the full armed planner.

## Reachable blockers and behavior

Split Shot is an ordinary Brute weapon. The previous projectile implementation
applied its center damage without the source body's forward push or either
perpendicular damage/push. It also lacked explicit Rust/Python effective upgrade
IDs. The new dedicated family branch retains the initial projectile endpoint,
applies the main forward hit, then the first side at `(dy,-dx)` and the second
at `(-dy,dx)`, with outward pushes. All four variants are represented: base/A
deal 2 damage; B/AB deal 3; base/B have one use and A/AB have two. This side
order is opposite Centipede's; translating direction indices directly would
reintroduce a rotation bug.

The shared damage, status, death and push routines remain the model boundary.
A synthetic first-side Shell Psion death makes subsequent armor damage depend
on order. Other tests distinguish the saved endpoint from a moved primary
victim, Mountain and empty-edge endpoints, shield/freeze/armor/ACID, and an
encoded zero-HP Building endpoint. The dedicated branch excludes Heavy Rocket,
whose three zero-damage neighbour pushes remain a separate unsupported body.
Passing these checks does not establish native corpse/explosion scheduling.

Artemis inherited targeting admits building centers. The planner previously
excluded them, and the simulator's shared legality check therefore rejected a
source-shaped sacrifice. Only the existing base/A Rust IDs are widened. In the
minimized fixture, an artillery mech whose movement is spent faces two queued
Fireflies beside a one-HP building. The remaining two buildings each have two
HP, and grid power is two. Shooting the center destroys one building and
pushes both enemies into Chasms, preserving the other buildings and one grid.
The building-immune A version preserves all three buildings and both grid.

## Evidence and reproduced failures

The [source evidence receipt](../data/solver_first/s1_player_aoe_411_evidence.json)
pins the owner Windows build 13725832, executable
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`,
the installed Lua source identities, inventory joins and line spans. The
installation includes a Mod Loader overlay; this is not a pristine-depot claim.
Published material contains normalized facts and game-relative identities,
without source bodies, binaries or identifying host paths.

The pre-fix Rust Split Shot regression failed because the center victim remained
at `(3,3)` instead of moving to `(4,3)`. Its stdout was observed during the
test run but has no retained byte receipt; the evidence labels that limitation.
The retained [v410 Artemis counterexample](../data/solver_first/s2_artemis_410_counterexample.json)
has raw SHA-256
`99d39977f4c6bb4a81b48a3b9ac296969b65b6926fd60d4f27f0e15377956446`
and loaded extension SHA-256
`35ce67e3f8048f406bdb3ef4339baeb9010aca3dc8ef98b94647ac0bb65b3c9a`.
Its center shot reports `illegal_weapon_target:3:3:Artemis Artillery`; after
the unchecked diagnostic enemy phase, grid is zero and only one building
remains. The old selected plan also omits the source-legal saving shot. These
are synthetic model counterexamples, not original-game before/action/after
observations or held-out practical evaluation.

No original Split Shot or Artemis selected-execution association, callback
return, immediate after-board or next-decision loop is admitted. Original
transition comparisons, fair archived admissions, held-out cases, campaign
evaluations and ledger/gate promotions are all zero for this tranche.

## Reference domain and guarantees

[solver_first_player_aoe.py](../scripts/solver_first_player_aoe.py) independently
enumerates each of the two exact Artemis fixtures: all ten in-bounds cardinal
shots at distance at least two, Wait, and full-HP Repair. It retains all twelve
choices and fails on any rejected Rust leaf. Exact fixture equality rejects
extra fields, different terrain/status, new actors, movement eligibility or
unsupported variants. With one actor and movement already spent, there is no
multi-actor primitive-interleaving reduction to assume.

Rust `score_plan` supplies transitions and default evaluation; `replay_solution`
supplies post-player and final projections. Neither is an independent original
transition oracle. The reference applies the existing clean postfilter:
compute the raw and player-building-clean maxima, then select clean when its
score gap is at most the larger of 5% of the raw absolute score and 500. Every
selected plan must belong to the independent leaf set and rescore with the
same objective. Both fixtures have zero score regret. The report also checks
sixteen Split Shot variant/direction post-player projections, including a
negative control outside the saved side footprint.

The JSON parser has no grid-defense input; an earlier fixture's
`grid_defense: 0` was ignored, including in the v410 counterexample. Final v411
fixtures omit it and declare the effective Rust default of 15% expected grid-save
credit. Actual resistance RNG and draw order are not modeled or admitted. Fixed
Chasm terrain drives the kills; the reference excludes environment modifiers,
pilots, spawns and mission modifiers rather than excluding that terrain.

The [frozen v411 report](../data/solver_first/s2_player_aoe_411.json) records
24 scored reference leaves, 16 matching Split Shot projections, source hashes
before/after and the loaded extension hash. Source snapshots identify inspected
files; they do not independently attest the build-to-extension relation. Inputs
are synthetic visible fixtures, not newly admitted fair archive observations.
The production result remains `best_found`, horizon one, with null certificate
and valid bounds. Reference agreement here cannot promote the full legal-action
domain or practical strength.

## Validation and version discipline

Both Rust and Python simulator pins are 411. The v410 tracked failure corpus is
archived as [failure_db_snapshot_sim_v410.jsonl](../recordings/failure_db_snapshot_sim_v410.jsonl),
raw SHA-256
`a5bf0a9b459e754a3bf9c49b5564c745687273aa04fafddd60e82d9de43f0b66`.
Pre-existing user changes to the live failure database and all other protected
files are preserved separately and are not staged with this tranche.

Final release Rust unit validation passes 1,032 tests. The v411 release wheel
is rebuilt and installed before Python integration and reference comparisons.
The final Python tranche passes 69 checks covering these fixtures, rejection
sensitivity, source receipts, earlier independent bounded search, determinism,
search accounting and retained Centipede return evidence. Six Rust integration
regression checks pass over the 1,052 tracked recorded-board corpus. The frozen
report is regenerated after the explicit configuration correction; reference
regret remains zero for both Artemis fixtures. The loaded extension hash and
final receipts are retained in the report rather than inferred from a version
number.

## Remaining scope and next milestone

- Artemis B/AB exist in shipped content but lack Rust IDs/mappings; do not
  substitute base/A or claim effective-loadout coverage for them. The u8 WId
  allocation now reaches 254; adding both variants requires an explicit wider
  representation/table/mask design rather than silently overflowing the enum.
- The Artemis usefulness filter still removes a building-only base shot with
  no adjacent unit. Source target membership is wider than planner retention;
  complete armed action retention remains unproved.
- Tank/Split Shot target membership delegates to native `GetSimpleReachable`.
  Four direction representatives and explicit fixtures do not establish that
  native target set or every projectile blocker/status interaction.
- Armed move/use operations can change another actor's position or survival.
  Permuting one compound move-then-use action per actor is insufficient for a
  complete primitive-interleaving reference. The prior disarmed commutation
  argument must not be reused for an armed multi-actor domain.
- Heavy Rocket pushes, CentipedeBoss trail ordering and wider native effect
  scheduling remain separate named gaps. No additional helper chain is claimed
  closed by this source review.
- Configuration and fair-information admission, full state continuity, frozen
  independent development/held-out corpus, practical budget/risk choices and
  campaign uncertainty remain governed by the original seven acceptance gates.

Continue: this tranche reproduces two reachable model failures and corrects
observable planner behavior. The next end-to-end milestone remains an original
selected action linked to its immediate outcome and enemy/environment/spawn
continuation. Any next armed search extension must independently enumerate
primitive interleavings or prove a valid domain-specific reduction first.
