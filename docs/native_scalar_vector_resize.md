# Native resize with larger scalar copies

The resize owner at RVA `0x002eb680` now executes its native allocation,
feature-zero scalar-copy and deallocation descendants for sampled live sizes
four through 256 eight-byte elements. Only successful HeapAlloc and HeapFree
responses remain supplied. The copy lengths span 32 through 2,048 bytes.
Old capacity equals live size or 512; requested capacity equals live size,
512 or 513. All 32 old and new block alignments occur in paired combinations,
across three stack alignments. This includes both metadata-based aligned
storage and ordinary small allocations.

The destination lies below the independent old source buffer. For destination Q
and length L, the prefix copies h=(-Q)&3 bytes, followed by floor((L-h)/4)
DWORDs and (L-h)%4 trailing bytes. At least 32 bytes remaining selects REP
MOVSD, followed by one exact dispatch-table read and the byte tail. Only a
four-element vector with an unaligned small destination falls back to the
short scalar loop. The feature reads precede payload access; both feature
words remain zero. Tables are verified as data, separately from instructions.

The existing allocation and deallocation oracles are rebased with native
continuations and joined to independently derived copy and owner events.
Copy returns EDX equal to the remainder for REP, or the final original DWORD
for the short-loop fallback. Free then supplies its declared volatile register
responses. Final EAX equals the new end; the original nonvolatile registers
return, ESP advances by eight, and arithmetic flags come from the owner's
stack cleanup. Allocation reaches owner ESP minus 76; copy saves state at
minus 44 and free reaches minus 68. No deeper copy frame is needed.

## Evidence and reproduction

Unicorn 2.1.4 matches 8,640 cases, all 46 owner sites and 248 executed sites
from 989 loaded instruction bytes and 366 static sites. An additional 32 table
data bytes are verified. Each case supplies one allocation and one free API
response. Ordered native accesses, full stack, object, old and new buffers,
metadata, feature pages, tables, globals and import slots agree with the oracle.
Ancestor and payload corruption controls fail at their intended memory checks.
Independent semantic review passed. Focused tests include exact CLI rebuilding.

Actual heap effects, failures, SIMD feature modes, arbitrary geometry and
larger payloads remain outside this checkpoint. No whole-program accounting
promotion occurs.

`scripts/itb_native_scalar_vector_resize_conformance.py` provides `build`,
`verify` and `verify-structure`. It takes the small-resize source flags with
`--scalar-copy` replacing `--small-copy`. Exact commands require `--executable`;
verification requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_scalar_vector_resize_conformance.json`.
Canonical SHA-256:
`2916af83679014cc7ba06402933ed3194e1d7240b0bcd121317926d93dc81a28`.
Raw SHA-256:
`ae391468f7f6d0250dfbfca0b0347fb414d215af64708b9fbb2069afd029d3e6`.
