# S1 archived tactical-cycle observations

The sealed August 29 spawn-coordinate capsule campaign supplies stronger
original evidence than the earlier partial Bombling move. Its three unarmed
control trials bind process identities to Windows build13725832 and the
documented executable hash. Each records three completed player actions,
confirmed native End Turn delivery, and a fresh Mission_Power turn-2 outcome.
They are repetitions of one scenario family, not three independent families.

The [offline importer](../scripts/solver_first_archived_turn.py) validates the
sealed receipt and thirty control artifacts before diagnostic replay in Rust
v409. The [report](../data/solver_first/s1_archived_turn_report.json) retains
all three attempts: 255 direct-getter projection checks, six differences, and
two rejected next-decision alignments. The one ready snapshot matches all 85
checks (three actors × seven fields, plus all 64 terrain tiles). This is a
partial endpoint projection through a recorded tactical cycle; it does not
establish complete transition equivalence, ordered events, legal actions, or
S1 completion. All seven acceptance gates remain open.

## Readiness defect and acquisition repair

Pair001/control exports all three mechs active at the next player turn.
Pair002/control and pair003/control export all three inactive despite
`phase=combat_player` and `turn=2`. Their six readiness differences remain in
the raw diagnostic denominator. Neither outcome establishes a ready next
decision. An early capture is a plausible explanation, not a proven event
timeline; no later same-control snapshot is sealed in this family.

The existing capsule acquisition script accepted a newer mission/player phase
after one fresh-generation read. Its source lacked an active-actor condition.
Source identity before the repair was SHA256
`cc405639e0962a646f76a976448770e099d0175be4cc5791c532cc6528c56b8c`;
this is a repository-source pin, not attestation of historical installation.
The archived trial's own `valid_trial=true` flag is not a substitute for the
new decision-state admission check.

The repaired acquisition requires exactly the immediately following turn and
waits on fresh reads within one shared time budget, including the refresh ACK,
for a living active player actor, including an armed controllable mission ally
or moving VIP Truck. It never retries End Turn. Timeout rejects capture instead
of admitting the last spent-actor snapshot. Mocked tests cover old-turn and
spent-actor generations followed by readiness, bounded timeout, strict Boolean
activity, dead actors, and non-mech allies. No live acquisition was run and no
sealed artifact was altered.

## Provenance and information boundaries

The campaign receipt binds each input/plan/outcome to its isolated session,
native delivery result, process executable SHA/size, restored start-state
manifest, inventory identity, and runtime helper identities. The cleanup receipt
attests the installed experimental loader hash
`93f99e8854e8f01bc0c64b0c07eff5aa1fe078f7e821a60de133db7ec375986c`,
which matches the retained loader source. This is the owner-modified installation;
it is not a pristine depot claim or a fresh independent runtime acquisition.

The control observer was unarmed, but native RNG was explicitly reseeded after
the player actions and before End Turn. The intervention belongs to the oracle
provenance. Historical full bridge/save/overlay/configuration inputs are used
only to replay the recorded fixed actions diagnostically. They are not supplied
to a planner. The provisional player-observation adapter rejects all three
inputs; fair provenance and configuration reconciliation remain unresolved.
Engine UIDs join historical oracle artifacts, not fair planner identities.

All related control/dormant/armed trials belong to development. No sibling trial
can serve as an independent held-out replacement. Canonical-input hashes are
hashes of sorted compact serialization; source pins separately bind raw artifact
bytes. Replay output is kept private, with a public hash and normalized checks.

## Differences that must remain visible

Rust's final board restores player readiness and advances the turn, but uses
stationary heuristic enemy requeue. The actual next decision also includes
enemy movement, new eggs/webbing, and spawn scheduling. The report retains
ungraded endpoint differences rather than deleting these fields to claim
full-state agreement.

For example, Rust retains ACID at bridge `(3,1)` (G5), while the original outcome
shows Centipede2 UID1251 there with ACID and no exported tile ACID key. The boss
also moves onto predicted-ACID rubble at `(3,3)` and becomes ACID-coated. This is
consistent with the existing landing rule consuming a ground pool during the
omitted repositioning interval. It is not an admitted Centipede rule mismatch.
Moreover, the exact loader omits tile ACID both when `IsAcid` is false and when
its protected getter fails. A missing key cannot establish a successful false
probe. The falsifier needs an original snapshot immediately after the attack,
before repositioning, and successful acid probes around arrival.

Captured grid power is 4 while the diagnostic replay predicts 2. The attested
loader reads `save_data.network`, with a GameData fallback, rather than a live
grid getter. The archive has no confirmed resistance event. This difference
therefore proves neither a Grid Defense resist nor a grid-accounting bug.
Effective next-turn max HP, moves, and weapons also need reconciliation between
raw bridge fallbacks and the input's save overlays. Status absence, extraction
freshness, and different update stages must not masquerade as rule failures.

## Tranche progress report

| Required dimension | Checkpoint |
| --- | --- |
| Build / solver / corpus / information / objective | Windows build13725832, owner modified; solver baseline `77356e13d344bd639899cb5c6653784732c5d60d`, v409; `s1-archived-capsule-development-v1`; historical oracle diagnostics only; recorded-plan fidelity, no objective change |
| Named blocker and scenario | Can the recorded Mission_Power movement/attack/effect cycle be compared at a ready next decision with known provenance? |
| Before → after supported behavior | Unversioned partial move → pinned full-cycle outcome snapshots; one ready partial endpoint projection; future capture now rejects spent actors |
| Original evidence and supplied boundaries | Sealed original bridge/process/delivery receipts; seed intervention and save overlays explicit; no original engine rerun |
| Attempted / admitted / passed / failed / excluded | Three diagnostic replays completed; 255 checks, six readiness differences; one ready projection with 85 matches, two alignment rejections; zero fair-input, complete-state, ordered-event, or legal-action-set admissions |
| Search status and valid bounds | No planner invocation, certificate, or new bound |
| Held-out outcome / latency / memory | No held-out evaluation or baseline/candidate practical comparison |
| Uncertainty / regressions / exclusions | Capture readiness repaired; raw original differences retained; no reproduced semantic bug; enemy repositioning, getter success, grid freshness and overlay reconciliation remain unresolved |
| Next milestone and work selection | Acquire an aligned original player/queued-enemy/effect/next-decision family with actual intermediate events and audited fair inputs. Prioritize existing materialized-effect captures and provenance reconciliation over the separate Lua VM/resource recreation. |

Validation: 53 focused tests pass across the grader, capsule trial/condition/
campaign, and bridge refresh/race tests. The grader's perturbation tests detect HP, terrain, and readiness changes and
reject missing direct getters or incomplete tile observations. These test
comparison sensitivity and extraction admission; they do not prove combat
semantics. The offline runner deliberately exits nonzero while retaining the
six raw endpoint differences. There is no simulator version change.

## Deferred Lua acquisition frontier

Source inspection identifies the exact installed x86 `lua5.1.dll`: 419840 bytes,
SHA256 `0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14`,
with embedded Lua 5.1.5 lineage. Its real `lua_pushvalue`, `luaL_newstate`, and
`lua_newstate` exports are RVAs13e0/4730/19ca0. Original setup `0xe37f4→0x4caa0`
calls the constructor at `0x4cab0` and stores its result at global VA896048.
These are source facts, with no new runtime admission.

The current one-module query machine does not execute this DLL, whose preferred
base also overlaps its supplied Board mapping. A real VM would still leave
Luabind/script-provider and stock emitter/image/cache construction open. Thus
closing the Ground-route animation boundary needs a distinct VM/resource tranche;
supplied Lua answers or disabling emitter images would not close it. Existing
original transition evidence is the more direct next priority for the solver.
