# Small backward memmove semantics

`src/observatory/native_movement_memmove_backward_semantics.py` predicts the
rightward overlapping scalar arm at the actual memmove entry RVA36E580.
The body is independently pinned to twelve atlas ranges,1330 bytes and
SHA8b0b052a9ad8d284940e5886d952cc89ebbcef586b2c46075afb6b4ce26dbc34.
Every selected literal instruction point is rebound to this entry; the whole
code page is76E000 and the conservative sparse envelope ends at76EAF4.

The five-input API returns the complete eleven-field state packet. Actual
cdecl count is2..31 and `source < destination < source+count`. Mapped,
nonwrapping overlapping extents are disjoint from the protected caller frame.
DWORD offsets descend as `N-4*(i+1)`, then leftover byte offsets as `r-i-1`.
Ordered reads reflect evolving memory, while a separate original-source blit
predicts every final page. The overlapping source region can change.

Final EAX is destination, ECX zero, EDX the original count, ESP advances four,
and all nonvolatile GPRs/eight XMM values preserve. Final defined flags are
0x44 under mask 0x8C5 when no byte tail executes, or mask 0x8D5 with a byte tail.
DF0 preserves. No imports, CPU feature reads, SIMD or STD/CLD execute in this
bounded arm. Trace/access counts are `24+7*q+6*r` and `9+2*q+2*r`.

Independent source review is GO. All37 selected instruction points matched
the actual memmove source independently. The frozen handwritten suite binds
full packets, all465 rightward count/shift pairs at sixteen alignments, ordinary
flags, direct pages versus descending replay, strict schemas, prewrite
rejection ledgers and detachment. All 8,216 independent checks pass without skips in 48.05 seconds.
All1,860 complete native cases agree across every valid pair/four alignments.

Counts32 and above, larger/SIMD paths, ownership, gameplay and broader native
receipt sealing remain separate work; whole-program accounting is unchanged.
