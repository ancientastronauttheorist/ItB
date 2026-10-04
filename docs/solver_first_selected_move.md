# Conditional selected Move producer acquisition

October 4, 2026. This advances the S1 corridor investigation from lower Lua
callbacks to the original native selected-target and effect producers. S1 and
all seven acceptance gates in [the plan](SOLVER_FIRST_PLAN.md) remain open.

The frozen development world passes: **221 original calls, 4,435,039
instructions**, with every call returning at the expected stack position and no
native failure. There are 574 byte-pinned source identities, 521 visited, and
15,324 observed Lua DLL instruction points. Those counts describe acquisition
coverage; they are not gameplay, corpus or gate denominators.

## Scenario and original producers

The inherited [Move callback fixture](solver_first_move_callbacks.md) supplies
the H8/G8/F8/E8 corridor, with Water at G8, Mountains outside the corridor, and
a declared Massive player actor at H8. Original getters produce movement budget
3 and profile 18. Full Pawn/Pilot/animation/equipment loading and deployed actor
availability remain excluded.

Original `2287b0` propagates the real Board interface through the genuine base
manager into its Move and Repair skills. Original `269cc0` validates the origin,
executes the target callback, retains the ordered G8/F8/E8 target cache and
returns a separately owned clone. Original `268920` writes the selected
coordinates and calls complete `268050`, which checks cached membership before
constructing the effect. Membership is produced by the original target query.

Two original callable constructors create an explicitly empty passive aggregate
and query string. A direct original `25e700` call returns `AL=0` for
`Passive_FriendlyFire` and destroys its genuinely constructed owned argument.
Both effect post-processors also execute. This closes the declared no-passive
query dependency. Complete global initializers `6cd0/6cf0`, their exit-handler
registration, CRT startup, gameplay population and guest teardown are excluded.
No reachable constructor instructions or result-producing calls are skipped.

The stock Lua `TwoClick` and `Explosion` property getters, normal
`Move:GetSkillEffect`, original `267710` metadata decoration and both `268340`
post-processors execute. The selected effect has:

- Origin H8, target G8, and a separately owned H8/G8 path.
- One 308-byte record: type 4, mode 0 and `FULL_DELAY` (`0xbf800000`).
- Native Move name, value 0, owner -1, empty animation, and record origin H8.
- Record position (-1, -1), empty secondary vector and zero metadata flag bytes.

Owner -1 and selected manager index -1 are actual base-manager defaults. This
does not attribute the effect to a loaded actor ID or submit a manager action.
Stored active and `bMoved` remain 0; HP remains 3 and position remains H8.
These are unchanged declared query cells, not proof of a ready deployed actor.

## Controls, retention and limits

The native setter rejects blocked D8 and occupied H8, writes the invalid target
sentinel and clears both effect vectors. A subsequent native H8/G8 selection
restores the graded effect. These four setter checks are dependent components
of **one corridor/world family**, not independent corpus cases. Wait/no-op and
all-action availability remain excluded. Temporary Move/Pilot strong counts
return to 1 and the Lua stack returns to 0. Guest registry/cache/skills/events
remain retained: 1,548 allocations requesting 102,316 bytes, with 2,853 Lua
allocator callbacks. Host graphics teardown is separate.

The earlier exploratory world passed 219 calls but lacked the final metadata
assertions and complete pre/post identity checks. It remains exploratory. One
preflight failure occurred before any native call when two complete initializer
windows were incorrectly treated as atlas owners; its driver and failure are
retained. The frozen runner excludes those unexecuted roots and explicitly joins
the callable constructor pins. No failed native world is omitted.

The frozen run retains all **19 exact source files under full relative paths**
before acquisition. It verifies source, whole game input, stock script, runtime
and instruction-map identities before and after execution. The per-call
30-second/2-million-instruction limits are emulator acquisition budgets, not
planner performance measurements. There is no new Rust replay comparison or
solver/simulator semantic change; the earlier 63-destination comparison retains
its previous conditional scope.

## Receipts and next dependency

- [Native receipt](../data/solver_first/s1_selected_move_20261004.json):
  SHA-256 `85677073b7615bf940a36a80f22c8e6a2d144511b2b388e4700c16d62b46e3fa`.
- Private trace receipt: SHA-256
  `33a765ac9344ba9e76824cce9e4fb81e19474410f282904fe945e2c613debbe7`.
- [Boundary](../data/solver_first/s1_selected_move_boundary.json): 42 complete
  body pins and 13 data windows.
- [Attempt history](../data/solver_first/s1_selected_move_attempts_20261004.json)
  separates the preflight failure, exploratory world and frozen current world.
- [Reproducible runner](../scripts/solver_first_selected_move.py), with explicit
  `--exe`, create-only `--private-dir` and create-only `--report` arguments.

Independent source review checked constructor scope, calling conventions,
metadata offsets, ownership and pin coverage before the frozen run. A subsequent
receipt audit checks counters, retained sources and normalized projections.

The next named dependency is original submitted-action stats/context handling
through `2689f0`, Board dispatch through `1610d0`, route and queue settlement,
and consistent actor accounting. Source-only follow-up shows that even one
normal Move `FULL_DELAY` record queues continuation state. Route installation
alone therefore cannot establish completion or the next decision state.

Completed original actions, full-turn comparisons, fair-input admissions,
held-out cases, search certificates, ledger promotions and gate promotions are
all **zero** in this tranche. Fidelity, information legality, search optimality
and practical strength remain separate claims.
