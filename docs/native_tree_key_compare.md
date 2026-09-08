# Native tree-key byte comparator

The call-free leaf at RVA `0x002e76a0` compares NUL-terminated strings as
unsigned bytes and returns whether the left string is less than the right.
Its 73 bytes and 30 instruction sites are pinned, along with six direct caller
sites in insertion helper `0x002e8300`. The caller's two code ranges are decoded
and checked against their combined body hash; caller behavior is not claimed.

The native two-byte loop has the same read footprint as ascending pairs of
left/right byte reads ending at the first mismatch or equal NUL. It reads the
right argument before the left argument. The memory-shaped NOP performs no
access. There is no null-pointer special case: readable terminated storage is
required. Bytes following the terminator remain untouched and unread.

Final EAX is the less-than Boolean. ECX encodes less/equal/greater as unsigned
-1/0/1, while DL holds the last compared left byte and EDX's upper 24 bits
remain unchanged. Other general registers are preserved. RET 8 consumes two
arguments and finishes at entry ESP plus 12. Defined arithmetic flags come
from TEST of ECX; AF is undefined. Both initial DF values are preserved.

An independent Python byte-order relation and ordered-read oracle match
Unicorn 2.1.4 across 5,408 cases: 2,496 less, 416 equal and 2,496 greater.
The corpus covers empty strings, odd/even terminators, high unsigned bytes,
long common prefixes, four paired string alignments, four frame alignments
and both DF values. All 30 sites execute. Complete source and stack pages,
registers, defined flags and read order agree. Mutations to an unread ancestor
word and source storage after the terminator fail at the intended full-memory
checks. Independent review passed. Focused tests include exact CLI rebuilding.

This is byte ordering, with no locale or Unicode collation claim. Missing
terminators, arbitrary aliases and insertion behavior remain outside the proof.
No whole-program accounting promotion occurs.

`scripts/itb_native_tree_key_compare_conformance.py` provides `build`, `verify`
and `verify-structure` with `--program-facts`. Exact commands need
`--executable`; verification needs `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_tree_key_compare_conformance.json`.
Canonical SHA-256:
`6d70712cc9751139147a5ea42940f20ccdf727d8d59274bed5acd7af1a099815`.
Raw SHA-256:
`ec0d434d44e01e09ed2dc52cfc3fce4f6b4bf38ed07bd056cc850c755f2fbbd3`.
