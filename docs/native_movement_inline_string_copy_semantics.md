# Inline string substring-copy semantics

`src/observatory/native_movement_inline_string_copy_semantics.py` predicts copying
a substring between disjoint 24-byte inline strings with capacity fifteen.
Five keyword-only inputs describe pages, GPRs, XMMs, installed return and
ordinary flags; actual caller words supply source object, offset and request.
Independent source review is GO; all 1,017 independent checks pass without
skips in 25.05 seconds. All 128 full-state executable cases agree.

Both source and destination lengths are zero through fifteen. Offset must be
at or below source length; unsigned requested count clamps to the remaining
source bytes. Complete objects and the conservative stack span are mapped,
disjoint and nonwrapping. Zero performs no memcpy call. Positive uses the
selected scalar copy at the actual frame and return continuation. Source
terminators are not read or required by this counted-byte law. Self-copy,
heap strings, growth, invalid offsets and unwind are separate arms.

The complete fourteen-field packet contains seven-field geometry, full ABI,
pages, ordered accesses, trace, defined flags, DF, endpoint, full source-object
snapshot, destination bytes, full memcpy packet and two prefix-inclusive child
states for positive count. Child geometry, complete terminal ABI, snapshot,
flags and exact ordered accesses bind to actual input pages before adoption.
Replay checks all reads, restricts writes and verifies complete final pages.
Canonical child instruction labels and trace length remain explicitly trusted
metadata; tests demonstrate valid transported changes alongside strong byte,
access, ABI and page corruption rejection.

The destination receives exactly the clamped substring, a NUL and updated
length; capacity, remaining padding and all source bytes preserve. Final EAX
is destination, ESP entry plus sixteen, nonvolatile GPRs and all XMMs preserve.
ECX is zero for positive count, otherwise offset. EDX is the last copied DWORD
or count for positive, otherwise incoming EDX. Final flags are `0x85` under
`0x8d5`; DF is zero. Zero executes 33 instructions/17 accesses. Positive
executes 47 owner instructions plus the child, and `32 + 2*q + 2*r` accesses.

Handwritten independent tests cover lengths, offsets, request clamping, all
ordinary flags, complete bytes/accesses/traces/ABI/checkpoints, strict schemas,
pre-child ledgers, nested forgeries, metadata trust, geometry and detachment.
Executable cases cover every source length zero through fifteen, empty/end/
interior offsets, requests zero/three/maximum and two alignments, comparing
complete pages, GPRs, XMMs, accesses, trace, flags, DF and endpoint.
No broader native corpus seal, ownership or gameplay claim follows;
whole-program accounting is unchanged.
