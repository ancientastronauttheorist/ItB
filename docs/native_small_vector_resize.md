# Integrated native resize for small live vectors

The resize owner now executes its allocation chain, short copy, deallocation
guard and free wrapper in one isolated machine state. The proof supplies
normal successful responses only at the HeapAlloc and HeapFree boundaries.
It no longer summarizes allocation, copy or deallocation helper calls.

The bounded domain has zero through three live eight-byte elements, sampled
old capacities zero, four or 512, and requested counts through 513. Old and
new storage are disjoint mapped blocks, with preceding raw-pointer metadata
for large allocations. Zero requested count returns null without HeapAlloc;
zero-byte native copy still executes and accesses no payload. Nonnull old
storage is independently freed, including an empty old vector.

## Joined state and payload contract

For owner entry S, the deepest allocation CALL reaches S-76; native short
copy saves EDI at S-40 and ESI at S-44; the deepest free CALL reaches S-68.
The complete ancestor interval [S-76,S+8), object, both data blocks, metadata,
heap word and import slots are checked. Final ESP is S+8, EAX is new end,
and original nonvolatile registers are restored. Null old begin leaves
ECX=EDX=zero; nonnull old begin retains the supplied successful free volatile
outputs. Final flags follow the native owner's branch-specific cleanup.

The new payload equals the original old live bytes. Old storage remains
byte-for-byte unchanged in this emulation because the supplied free response
has no memory effect. New slack is preserved except for the native large
allocation metadata write. The owner publishes capacity, end and begin after
the native deallocation return. The proof requires disjoint nonwrapping
storage and normal API responses preserving all modeled memory.

The sealed independent allocation and deallocation oracles are rebased with
explicit replacement of their caller-return events by the actual native
owner continuations. Fresh outer-frame and forward DWORD-copy equations
connect their complete states. Only the shared synthetic import boundary is
hooked; the native continuation distinguishes allocation from free.

## Evidence and reproduction

Unicorn 2.1.4 checks 5,120 cases, executing 187 sites from 662 loaded bytes
and 255 static sites. All 46 owner sites execute. There are 4,608 supplied
allocation responses and 4,608 supplied free responses, with zero opaque
instructions. Every block alignment is sampled in a declared paired pattern,
across four stack alignments; this is not the full old/new alignment product.

Full stack, object, payload, metadata, global and IAT memory, ordered native
accesses, general registers, defined arithmetic flags and clear DF are checked.
Targeted ancestor-argument corruption and post-copy payload corruption are
both rejected. Independent review passed and all 49 focused tests passed,
including a complete exact-executable CLI rebuild.

Actual API execution, failed/retried allocation or free, larger live copies,
arbitrary aliasing and whole-program equivalence remain outside this proof.
No accounting promotion is claimed.

`scripts/itb_native_small_vector_resize_conformance.py` accepts `--owner`,
`--allocation-composition`, `--allocation-conformance`, `--small-copy`,
`--deallocation-composition` and `--deallocation-conformance`, with `build`,
`verify` and `verify-structure`. Exact commands require `--executable`;
verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_small_vector_resize_conformance.json`.
Canonical SHA-256:
`d4782f1090f4b946000fecdca97898e6eb803acc477541e0891df01767c59a39`.
Raw SHA-256:
`7b7f3499677624b810bf0b1cd6b1cd554584498b2888877033ac0e0540fe6dd0`.
