# Integrated append with native relocation

The append slice at RVA `0x002eb1bb` through `0x002eb21a` now executes its
native growth, resize, allocation, short-copy and deallocation descendants.
Only successful HeapAlloc and HeapFree responses remain supplied. This closes
the previous opaque growth delegation for the bounded successful append domain.

Cases contain zero through three live eight-byte elements. Full vectors grow;
capacity-four vectors append directly. Arguments are either the first or last
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
checks 3,584 cases and 234 executed sites from 851 loaded bytes and 331 static
sites. These include 1,920 resizes, 1,920 allocation API responses and 1,664 free
responses. Ordered memory accesses, general registers, defined flags, clear DF,
full object and buffer pages, external argument pages, globals and imports agree.
Ancestor and payload mutation controls fail at their intended checks.
Independent semantic review passed. Focused tests include an exact CLI rebuild.

The parent tree prefix, cookie epilogue, larger live vectors, failed API paths,
arbitrary geometry and actual heap effects remain outside this checkpoint.
No whole-program accounting promotion occurs.

`scripts/itb_native_small_vector_append_conformance.py` accepts the integrated
growth CLI source flags plus `--growth-conformance` and `--append`. Commands are
`build`, `verify` and `verify-structure`. Exact commands require `--executable`;
verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_small_vector_append_conformance.json`.
Canonical SHA-256:
`d1c606a60b79315b5605cb48bf7506a7454a248153af3a30c5fc211fde4277ed`.
Raw SHA-256:
`6e54443228c3b2082dc7976ee52de0e5e6ee9ec2063a4e4877f43e82d3e2e18b`.
