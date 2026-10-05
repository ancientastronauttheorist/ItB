# Ordinary Pawn constructor input boundary and failed acquisition

October 4, 2026. Windows build **13725832**, simulator **413**, source baseline
`5cfb26bdc451f511702d7faf00f6b5ac40d2517a`. The
[normalized receipt](../data/solver_first/s1_ordinary_constructor_inputs_20261004.json)
retains the source boundary and first failed fresh acquisition for the stock
PunchMech **H8-to-G8** scenario. S1 and all seven acceptance gates remain open.
This is an offline validation oracle; fair planner inputs, objective weights and
Rust semantics are unchanged.

The [complete Pawn constructor boundary](solver_first_pawn_constructor_boundary.md)
requires ordinary resource and Animation inputs before genuine actor-owned Move
and Repair can be acquired. This tranche pins the missing regex, graphics,
native string and Point interfaces instead of supplying their final outputs.
It does not establish a ready actor or an accepted movement transition.

## Actual acquisition and retained failure

One fresh world attempted **225 original call roots** and recorded **4,436,573
instruction visits**. The first 224 roots returned with correct stack cleanup
and no recorded failure. Root 225, CRT initializer `0x0038ee3b`, failed at
`HeapAlloc` CALL `0x00388c77`, return `0x00388c7d`, IAT `0x003d6220`.
These roots are one dependent execution history, not 225 independent cases or
224 accepted gameplay transitions.

The ordinary input continuation never started. Neither regex construction nor
any of the planned 26 resource producers, 78 asset predicate queries, nine
predicate control queries or two missing-resource lookups executed. Those
planned cases remain excluded as unacquired after prefix failure. Two earlier
prefix resource outputs are recorded separately and are not new ordinary
resource admissions. The world retains its failed status, complete trace and
allocation history. It was not resumed or retried in this tranche.

The actual graphics context was released, all tracked textures were deleted,
and cleanup reported no errors. Pre/post source, runtime and game-input
identities match; all **122** frozen source copies, **54** prior source identities
and **13** protected user files were verified. The executable, DLL, archive and
12 stock-file hashes remain in the receipt. A launch-guard filename error stopped
before any world was created; it is retained separately from this one native
failure.

## Diagnosis and separate runtime candidate

Runtime03 intercepted every `HeapAlloc` before inherited CRT dispatch. Its
ordinary allocation route accepts return `0x00389463` and flags 0, so it rejected
the already pinned CRT allocation route. The inherited source contract calls
for heap `0x12345678`, flags 8 and **868 zero-filled bytes** for the PTD. No
successful response for that failed import was manufactured or recorded.

Runtime04 extends only the exact ordinary malloc/free returns
`0x00389463`/`0x00389172`; other callers retain inherited IAT, opcode, frame,
argument and ownership checks. Independent source review confirms that only
dispatch changed. **13 synthetic checks** reproduce the predecessor failure,
exercise the corrected inherited calloc and ordinary allocation/free paths,
and reject wrong flags, count, heap, trace, IAT, unknown callers, oversized
requests and dead frees. Runtime04 has **zero original executions**. Its native
dependency closure remains pending; this correction does not change the failed
world into a pass.

The ordinary prototype heap is a declared **16 MiB**, monotonic, no-reuse success
service with an inclusive **1 MiB** Win32 malloc/realloc request limit. The Lua
request limit remains exclusive 1 MiB. The inherited CRT PTD service retains
its original 4 MiB prefix budget. Liveness/extent guards and the exact narrow
Lua terminal-word padding-read allowance remain intact. Fresh realloc tail
bytes are supplied. This is neither native Windows allocator identity nor a
certified complete-factory budget.

## Source and reference progress

The boundary pins **66 body rows representing 63 unique complete bodies**,
data windows, exact stock-source slices and the following interfaces. These
are source facts and planned checks, not acquired native outputs.

| Input or producer | Required original behavior |
| --- | --- |
| Pattern getter `0x0004d550` | Genuine Lua wrapper, output string plus two owned 24-byte strings; `RET52`, actual string contents and balanced Lua stack |
| Regex constructor `0x000c6ef0` | Fresh 20-byte receiver, borrowed native pattern string and flags 1; `RET8`, genuine compiled root/facet/locale ownership |
| Predicates `0x000be060`/`0x000be120`/`0x000be1b0` | Owned full image key, `RET24`; grade **AL only**, retain high EAX bits without assigning Boolean meaning |
| Ordinary loaders `0x000bee20`/`0x000c0eb0` | Actual PNG bytes, length and owned key, `RET32`; live resource/cache owners, full GPU pixels and metadata |
| Cache lookup `0x000be8f0` | Native stripped-key ownership, primary/advanced lookup, shared fallback wrapper and persistent missing marker |

Two exact pattern assignments are pinned by whole-file and slice hashes; their
literal expressions remain private. A null regex root is not accepted as
pattern initialization. The planned loader grade requires all 26 signed Point
Location pairs: eight stock shield offsets and 18 absent-key sentinels in the
explicitly sliced Location world. It also requires checks of stripped wrapper names,
consumed by-value heap-string retirement, resource flag/UV fields and real
texture readback; unwritten resource padding is excluded.

The source resolves the earlier outline crop uncertainty: primary and outline
uploads retain full dimensions, with **content-center metadata**, rather than
a physically cropped texture. The white mask comes from the original pixel
predicate over the center and eight neighbors. The x center uses ceiling;
the y center uses truncation. Four independently authored source-law masks
were recomputed byte for byte with their bounds and centers. They are expected
references, not original-game observations. The finite source x87 instruction
is `FRNDINT`; earlier private packet prose misspelled it.

Seventeen prior synthetic runtime checks and a real hidden host OpenGL smoke
test verify exact scalar parameter readback **9728.0**, a synthetic 1-by-1 RGBA
texture and context cleanup, including setup failure. That host API result
does not establish execution of the ordinary game loaders. Source inventory
finds both primary and advanced paths absent for the two missing keys; actual
fallback traversal remains unacquired.

## Tranche exit and next join

The tranche removed source uncertainty and reproduced a supplied-runtime fault.
Its single native attempt is **failed**, with **zero** new ordinary-resource,
factory, positive-actor, full-action, full-turn, fair-input, held-out, search,
ledger or gate admissions. Search status is **not evaluated**, valid bounds
are absent, and no held-out latency or strength comparison was run.

Stop this acquisition after its first failure. A subsequent bounded tranche
may test the explicit hypothesis that inherited dispatch preservation lets a
new fresh world reach the ordinary input producers, after current source and
review pins are frozen again. The factory still precedes equipment, placement,
activation, guarded Move consumption, repeated-Move rejection, retained Use
eligibility and full-turn enemy/environment/spawn continuity. The
[actor eligibility frontier](solver_first_move_actor_eligibility.md) remains the
integration contract; resource success alone cannot satisfy it.
