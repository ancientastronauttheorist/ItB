# Small forward memmove semantics

`src/observatory/native_movement_memmove_forward_semantics.py` predicts the
forward scalar arm at the actual memmove entry RVA36E580. This is the entry
called by inline string erase RVA8410. Its separate twelve-range1330-byte body
has SHA8b0b052a9ad8d284940e5886d952cc89ebbcef586b2c46075afb6b4ce26dbc34.
Selected relative instruction points match the previously reviewed forward
copy arm, with independently rebound literal addresses and code geometry.

The five-input API returns all eleven state fields. Counts0..31 accept mapped
nonwrapping disjoint, self or leftward-overlapping buffers; rightward overlap
selects the separate backward arm. Zero may use null/unmapped pointers. Caller
stack protection applies to actual extents, allowing disjoint unread gaps.
Ascending DWORD then byte accesses copy the original source snapshot into the
destination, including legitimate source-region changes under overlap.

Final EAX is destination, ECX zero, EDX last copied DWORD or count when there
is no DWORD, ESP advances four, and all nonvolatile GPRs/eight XMM values
preserve. Defined flags are 0x44 under 0x8C5 without a byte tail or8D5 with one;
DF0 preserves. Complete pages, ordered reads/writes, caller saves and return,
literal trace, original snapshot and endpoint are bound. No CPU feature
reads, imports, SIMD, STD or CLD execute on this selected arm.

Independent source review is GO. All4,966 independent checks pass without
skips in84.90seconds. The handwritten eleven-field oracle explicitly relocates
every selected instruction point and binding; expected packets do not come
from production code. It checks full pages/direct byte equations, overlap
reads, flags, strict schema/domain rejection ledgers, detached outputs and
caller gap geometry. All1,984 complete native self/leftward cases agree across
counts1..31 and four alignments.

Larger/backward/SIMD arms, ownership, gameplay and broader native receipt
sealing remain separate gates; whole-program accounting is unchanged.
