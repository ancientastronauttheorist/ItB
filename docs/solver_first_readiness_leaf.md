# Original stored-readiness setter boundary

The original `Pawn:SetActive` body now has six successful offline executions
on explicitly supplied receiver storage. The
[create-only report](../data/solver_first/s1_readiness_leaf_20261003.json) records
the original return, field accesses, changed bytes, trace hashes and exact
source/runtime identities. This removes the setter-mutation uncertainty behind
the bridge's `SKIP` operation. It admits no complete Wait action, legal action,
original gameplay transition, or tactical loop. All seven acceptance gates in
[the goal](SOLVER_FIRST_PLAN.md) remain open.

The solver-facing question is whether the original `SetActive(false)` mech
branch changes only the stored active byte. The original Windows build is
13725832, executable SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The body is RVA `0x002375f0`, 83 bytes, SHA256
`247eccc6d4587cf6101b169dfd98bc1ea9d20582a8fb27330ae9c6be3f336554`.
`ECX` supplies receiver storage and one stack word supplies the requested byte;
the original `RET4` must return with the expected cleanup. EAX/AL is not treated
as a success result. No helper or import ran in any of the six cases.

Each case supplies 4,608 patterned receiver bytes, stored active at `+0x91c`,
the setter gate at `+0x10c0`, and mech byte 1 at `+0x9e4`. These are storage
premises, not a complete original Pawn constructor. Disable and enable change
only `+0x91c`; repeated requests and both gate-zero controls change no bytes.
All 2 MiB of supplied world storage are compared before/after. Guest accesses
are restricted to reviewed receiver bytes and stack storage; unchanged
callee-saved registers, original instructions, return and stack cleanup are
checked. The emulator limit is 100 instructions per case and ten seconds,
with the pinned Unicorn 2.1.4/Capstone 5.0.7 runtime identities in the report.

The measured counts are six attempted, six admitted setter invocations, six
passed projections, zero failures, zero mismatches, zero case exclusions.
Domain exclusions are separate: complete constructors, original `IsActive`,
nonmech helper branches, Wait UI/callbacks, movement/weapon consumption, turn
reset and enemy/environment continuation. Held-out outcomes, search quality,
latency distributions and memory comparisons were not evaluated. The native
oracle is kept outside planner input.

The independent source review pins the `SetActive` registration at
`0x27c409/0x27c41f/0x27c426`. It also resolves a previous field ambiguity:
the route installer byte `+0x91e` is **Pushable**, loaded at `0x22c5d1` from
the `Pushable` property, rather than an action-readiness field. Movement-spent
state is separately archived as `bMoved` at `+0x99e`.

Ordinary skill submission is the next consumption boundary. The registered
`FireWeapon` virtual entry resolves to `0x237730`, 522 bytes, SHA256
`ef2b5bfdba77a599c1ebbc26d445513c88f102b3a532a50e8f118d6a8857f5da`.
Static review observes that successful selected-index-0 submission sets
`bMoved`, preserving stored active on the declared ordinary team-1/bonus-zero
branch. Equating index 0 with Move still requires genuine loaded SkillManager
ordering. Successful nonzero submission clears active before special ability
reactivation paths. Route installation/coordinate relocation alone does not
prove either consumption law. Direct Lua submission and ordinary UI admission
also remain distinct.

Those source facts have zero new runtime admissions. The private review packet
SHA256 is `5356d082377c89271a046f3b56b38fa69bea3b7474922e2942ee5029b12e51ac`.
`IsActive` at `0x23e8b0` needs genuine SkillManager/shared ownership in addition
to the active byte. `FireWeapon` resolves and submits actual skill effects;
substituting a successful return would manufacture the missing evidence. The
Ground route remains blocked at original Lua/resource setup. These are named
reachable dependencies, not reasons to promote a storage leaf to S1.

Continue: this bounded tranche removed a named setter uncertainty and corrected
the movement-field identity. The next end-to-end milestone remains a joined
original admitted move/use, immediate ordered outcome, and enemy/environment
continuation with content, overlay and information provenance. The
[archive audit](solver_first_archive_acquisition_audit.md) separately identifies
why the closest retained logs do not yet supply that join.

Reproduce without live play:

```text
python scripts/solver_first_readiness_leaf.py --executable <pinned-Breach.exe> --runtime-path <pinned-emulator-package> --output <new-report.json> --private-output-dir <new-private-directory>
```
