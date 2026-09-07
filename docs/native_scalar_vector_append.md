# Native append with larger scalar relocation

The append slice at RVA `0x002eb1bb` through `0x002eb21a` now executes its
native growth, resize, allocation, feature-zero scalar-copy and deallocation descendants.
Only successful HeapAlloc and HeapFree responses remain supplied. This closes
the previous opaque growth delegation for the bounded successful append domain.

Cases contain sampled live sizes four through 256 eight-byte elements. Full
vectors grow; capacity-512 vectors append directly. Arguments are either the first or last
aligned live element or one of two independent external pages. Both external
classification branches are covered, including the path that retains entry ECX
as the unused growth argument. An internal argument becomes an element index
before growth, then resolves against the new begin pointer. Native reads from
old storage after the supplied free response are rejected.

Slice ESP S and EBP S+32 place the owner local at S+20. The vector starts four
bytes into that owner. Growth enters at S-8, resize at S-28, the allocation API
at S-104 and free at S-96. Growth consumes its unused argument; the append
slice exits before the cookie epilogue at unchanged ESP S. The complete mapped
ancestor stack, including the owner local, is checked.

Copying performs read word zero, write word zero, read word one, write word one,
then increments the vector end by eight. Final EAX holds word one; ESI names
the owner; EDI is the internal element index or the original external pointer.
Internal ECX names new begin and EDX the append destination; external ECX names
the destination. Final defined arithmetic flags come from the memory ADD.

## Evidence and reproduction

The sealed independent growth oracle is rebased with the native internal and
external continuations, then joined to fresh append equations. Unicorn 2.1.4
checks 11,520 cases and 297 executed sites from 1,178 loaded instruction bytes and
442 static sites, with 32 table data bytes verified separately. These include
5,760 resizes, 5,760 allocation API responses and 5,760 free responses. Ordered memory accesses, general registers, defined flags, clear DF,
full object and buffer pages, external argument pages, stable zero feature pages, immutable dispatch tables,
globals and imports agree.
Ancestor and payload mutation controls fail at their intended checks.
Independent semantic review passed. Focused tests include an exact CLI rebuild.
All block alignments occur in paired combinations across three stack alignments.

The parent tree prefix, cookie epilogue, larger live vectors, failed API paths,
arbitrary geometry and actual heap effects remain outside this checkpoint.
No whole-program accounting promotion occurs.

`scripts/itb_native_scalar_vector_append_conformance.py` accepts the integrated
scalar growth CLI source flags plus `--growth-conformance` and `--append`. Commands are
`build`, `verify` and `verify-structure`. Exact commands require `--executable`;
verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_scalar_vector_append_conformance.json`.
Canonical SHA-256:
`df08d84b1392a9566a6c0f89b65332515e5faa1ca252c04718f6d8fcc69fcdcb`.
Raw SHA-256:
`1de4da3785696e126a052ece4c9588692a83985bfb83b553612f0b05f6453c23`.
