# Conditional Move queue settlement

October 4, 2026. The named development case remains stock **H8-to-G8 Move** on the Ground/Water corridor. The solver-facing question is whether original metadata/delay queues settle without changing the actor or particle state, and whether Board activity 0 still rejects Move for the supplied inactive actor. Windows build `13725832`, the installed overlay, stock scripts/resources, solver baseline `84c186ae` and simulator 413 remain pinned. The preservation objective stays provisional. **S1 and all seven acceptance gates remain open.**

## Acquired behavior

One fresh joined world completes the prior conditional submission grade, then calls original Move availability, Board activity, queue update, Board activity and Move availability in that order. All **317 original EXE/DLL calls and 32,895,526 instructions** return with correct stacks and no call failure. The [receipt](../data/solver_first/s1_move_queue_continuity_20261004.json) binds every tail call to its actual entry, receiver, arguments, return, trace and import digests. Original queue updater EAX has no assigned success meaning; Move availability is a Boolean in AL.

Original Board activity `0x001698f0` returns **6 before settlement and 0 afterward**. Original `0x00169bf0` takes the empty-primary FULL_DELAY(-1) branch, visits native metadata erase/destruction and delay memmove, and decrements the two queue ends. Both queue begins, capacities and live allocations remain retained. There are exactly two tracked queue writes, with no tracked actor or selector write. All 64 Tiles are visited in original column/row order three times: 192 activity encounters.

Before and after this settlement, original Move predicate `0x00234cd0` calls original `IsActive` and returns **AL false** for the same stored-inactive Pawn. Actor position G8, HP 3, stored activity 0 and `bMoved` 0 remain unchanged, as do Stats, history, path/shared owners, the other activity queues and the complete captured Board/Tile input footprint. The registered actor vector remains empty. Conditional Board activity 0 therefore supplies no available action or next player decision.

The fresh receipt records actual final emitter DWORD cells, flag, draw-resource pointer, strict native 144-byte emitter and 68-byte draw ownership, all 32 typed particle rows and the storage digest. The sealed private world retains the full 1,408-byte particle storage. They are unchanged through metadata erasure. Active velocity and padding remain independently ungraded; padding is retained as readback only. The private storage reproduces the recorded typed cells and digest. This new capture does not retroactively repair the [earlier completion receipt's retained-data limits](solver_first_move_submission_completion.md).

The final original Lua getter runs after both availability queries and queue settlement on the same Lua state and returns 0. Fifty-four frozen source copies match current sources and preflight/postflight records, with equal runtime and installed-input identities. Independent review covers the saved world. Twenty-three inert receipt controls check source/runtime identity, same-state final getter, AL interpretation, native root and live owner/storage admission; they are reader sensitivity checks, not original transitions. Host graphics teardown completes separately; retained guest objects cannot resume afterward.

## Supplied boundaries and counts

The one named input change is the no-selection sentinel at Board `+0x2d68`: original Board construction writes FFFFFFFF, while the earlier raw fixture supplied zero. This fresh fixture declares FFFFFFFF immediately after initial WORLD construction, before any native query, selection or submission. Full Board construction is excluded. No observed blocker, output, actor activity or particle state is patched. Prior supplied runtime, resource, heap, Animation and actor/query boundaries remain.

| Subsystem | Observed scope | Result |
| --- | --- | --- |
| Fresh conditional submission and queue acquisition | 1 attempted, 1 admitted, 1 matched, 0 failed | All output and call grades pass |
| Negative Move availability | 2 original calls on the same inactive actor | False before and after settlement; no positive action admission |
| Activity encounters | 3 ordered traversals of 64 Tiles | 6 before and 0 after |
| Rust differential replay in this tranche | 0 new cases | Prior conditional position/HP comparison remains separate |
| Genuine ready actor and complete legal action | Same development fixture excluded | Raw inactive actor, empty registry and incomplete ownership/deployment |
| Full turn, fair inputs, held-out corpus, search and gates | 0 admissions | Remain open |

This is one shared development family, not an independent or held-out family. Emulator calls/instructions measure acquisition work; no planner latency, memory, practical outcome, win rate, bound or optimality is evaluated. Rust semantics and simulator version are unchanged.

## Next integration exit

The [actor eligibility frontier](solver_first_move_actor_eligibility.md) identifies genuine Pawn-owned inherited manager, Move/Repair shared owners, context/identifier propagation and the guarded selection/confirmation path. The existing separate base manager cannot substitute for the same Pawn's component ownership. A smaller original component construction may close that conditional boundary, with full loading/deployment still excluded.

The next useful exit is actual actor-owned readiness and guarded selection, Move consumption, repeated-Move rejection and retained Use eligibility, then queue settlement into an actual next decision. Enemy/environment/spawn continuity follows. This tranche stops after its one predeclared fresh acquisition: queue settlement and negative availability remove the named ambiguity, while further helper work requires a concrete blocker in that integration.
