# Small forward copy including overlap semantics

`src/observatory/native_movement_small_forward_copy_semantics.py` predicts the
forward scalar arm at CRT entry RVA3703E0 for counts zero through31. Positive
copies allow disjoint buffers, destination equal to source, or leftward
overlap. Rightward overlap selects the separate backward arm and is rejected.
Mapped, nonwrapping extents and the caller stack must be disjoint; disjoint
buffer gaps may contain the stack or return address. Zero needs no mapped
source/destination bytes and accepts null or unmapped caller pointers.

The five-input API returns the complete eleven-field packet: geometry,
registers, XMMs, all pages, ordered accesses, literal instruction trace,
defined flags/mask, DF, endpoint and the original source snapshot. Ascending
DWORD copies precede ascending leftover bytes. The final destination equals
the original source bytes. An overlapping source region can legitimately
change. Saves of ESI/EDI and the caller return are included in complete replay;
all nonvolatile registers and eight XMM values preserve.

Final EAX is destination, ECX zero, EDX the last DWORD value when any DWORD
copies occur (otherwise count), and ESP advances four. Defined final flags
are 0x44, with mask 0x8C5 for no leftover bytes or8D5 after a byte loop; DF is zero.
Accesses number `9 + 2*q + 2*r`. Positive instruction count is
`24 + 6*q + 6*r + 2*(r!=0) + 2*(destination>source)`; zero uses
`18 + 2*(destination>source)`. CPU feature globals and larger SIMD branches
are not executed in this domain.

Independent source review is GO. All4,966 independent checks pass without
skips in45.44seconds. All1,984 complete native self/leftward overlap cases
agree across counts1..31 and four alignments. Tests retain2,115 prior cases,
add overlap flag recipes, all465 rightward rejection pairs, complete evolving
reads and separate direct final-page laws, caller gap geometries, strict input
schemas, rejection write ledgers and detachment. Review corrected an unnecessary
convex-hull restriction; the existing disjoint-copy artifact is unchanged.

Sparse body identity is pinned to twelve atlas ranges/1330 bytes. Larger,
backward, SIMD, ownership, gameplay and native receipt corpus work remain
separate gates; whole-program accounting is unchanged.
