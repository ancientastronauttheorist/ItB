# Small disjoint scalar copy semantics

`src/observatory/native_movement_small_memcpy_semantics.py` predicts the scalar
zero-through-31-byte branch at the selected CRT copy entry. Its five
keyword-only inputs describe actual pages, GPRs, XMMs, installed return and
ordinary flags. Cdecl caller words supply destination, source and count.
Independent source review is GO; all 2,117 independent checks pass without
skips in 17.93 seconds. All 256 executable cases agree.

Positive source and destination extents are fully mapped, disjoint and
nonwrapping, separated from the protected caller/saved-register stack span.
Zero may carry null or unmapped pointers and needs no source/destination pages.
Selected code pages and actual return are separated from input data. Counts
32 and above, overlapping/backward copies and SIMD dispatch are separate arms.
This scalar branch reads no CPU-feature globals and calls no helper or import.

The complete eleven-field packet describes four-field geometry, full ABI,
pages, ordered accesses, instruction trace, defined flags, DF, endpoint and
source snapshot. It copies `q = count // 4` DWORDs followed by `r = count % 4`
bytes, with `9 + 2*q + 2*r` ordered accesses. Pointer order determines whether
the prefix includes the second end comparison. Zero traces have eighteen
instructions plus two when destination exceeds source. Positive traces have
`24 + 6*q + 6*r + 2*(r != 0)`, plus those same two prefix instructions.

Final EAX is destination, ECX zero and EDX the final source DWORD when q is
positive, otherwise count. ESP advances four bytes; cdecl argument words,
nonvolatile GPRs, all XMMs, source bytes and unrelated pages preserve. Final
flags are `0x44`: mask `0x8c5` for zero or no byte tail, excluding undefined
AF, and `0x8d5` after the tail's final DEC defines AF/OF. DF remains zero.

Handwritten independent tests cover all counts, alignments, pointer orders,
ordinary flags, exact bytes/accesses/traces/ABI, strict schemas, pre-write
ledgers, zero exemptions, broad geometry and detachment. Executable probes
cover all 32 counts, both pointer orders and four alignments, comparing every
page, GPR, XMM, access, trace, defined flag, DF and endpoint.

The full selected body is identified by the atlas's twelve sparse ranges,
1,330 concatenated bytes and body hash; that size is not a contiguous extent.
Program-facts provenance is pinned. V2 only adds this provenance metadata to
the source validated natively as V1. No native corpus seal, larger/overlapping
copy law, allocator ownership, gameplay or whole-program promotion follows.
