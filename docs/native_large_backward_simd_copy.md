# Larger backward SIMD copy

This checkpoint extends the backward-overlap proof at copy entry RVA
`0x0036e580` to lengths 128–2048. It requires source < destination <
source+length, representable unsigned 32-bit exclusive buffer ends, clear
entry DF, and bit one set in the stable feature DWORD at RVA `0x00493f30`.
MOVDQU/XMM architectural execution is available. Mapped buffers remain
separate from protected stable frame, code and feature storage; all byte
alignments are permitted without overread.

Suffix bytes are copied backward until the destination exclusive end is
16-byte aligned. Each descending 128-byte block then loads all eight source
vectors before storing any vector. Descending 32-byte blocks use two loads
before two stores, followed by a descending scalar tail. Destination equals
the original source snapshot, including destructive rightward overlap;
every other payload byte remains unchanged.

The last 128-byte block replaces XMM0–7 with its original source vectors.
Later 32-byte blocks replace only XMM0 and XMM1. If alignment leaves fewer
than 128 bytes, XMM2–7 preserve their entry values. EAX returns destination,
ECX is zero, EDX remains original length, and other general registers restore.
Cdecl return advances entry ESP by four. CF/OF/SF are zero, PF/ZF one; AF is
undefined when the post-alignment count is divisible by four, otherwise zero.
DF remains clear.

## Evidence and limits

The normalized graph model covers 82 sites and 291 bytes in 4,864 cases.
Exact Unicorn 2.1.4 replay covers the same sites in 4,352 cases. Its source
matrix crosses a mapped page boundary and includes all 16 byte alignments,
four overlap distances, two frame alignments and two feature-word samples.
Both independent reviews passed. The full pinned function witness remains
404 sites and 1,330 bytes; other dispatch paths are outside this proof.

Independent checks cover all eight XMM registers, general registers, defined
flags, DF, complete payload/stack/feature storage, and ordered byte, scalar
word and vector accesses. The pinned emulator exposes each architectural
16-byte transfer through two ordered 8-byte hooks; the oracle preserves
the eight-load-before-eight-store sequence while matching those hooks.
Three semantic mutation controls and separate replay payload/XMM corruption
controls are rejected.

No forward path, greater length, alternate feature dispatch, overread
permission, actual game execution, complete copy-library equivalence or
global accounting promotion is claimed.

## Reproduction

`scripts/itb_native_large_backward_simd_copy_semantics.py` takes
`--program-facts` and `--backward-simd-copy-semantics`; the conformance script
takes `--semantics`. Both support `build`, `verify` and `verify-structure`.
Exact commands require `--executable`; verification requires `--evidence`.
JSON is deterministic UTF-8/LF, including binary stdout on Windows.

`tests/test_itb_native_large_backward_simd_copy.py` checks independent
snapshot/XMM boundary relations, malformed input, sealed receipts and gated
exact CLI rebuilds. All 42 tests passed, including both exact CLI rebuilds.
Set `ITB_EXACT_EXE` to the pinned executable and put the
private Unicorn runtime `.local_decompile/fill_runtime` on `PYTHONPATH` to
enable the exact checks. Executable and runtime bytes remain private.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_large_backward_simd_copy_semantics.json`: canonical
  `d111aeafa33b9eb54197008e27fb44b97c3151a3a726909637e32ab1ead9de57`;
  raw `d3c8b5ac44f59ff52cc9d1b71db36c2f72b74ae9a2d6b0ec0413ab37538da473`.
- `native_large_backward_simd_copy_conformance.json`: canonical
  `d14a3ebfe55f89f4d60f06686343af07258c94d750f462150476671fd228df91`;
  raw `51dd42926ed664503e87c0812d0ed3bca7e655ebb489fd1fd59c57fe706772d4`.
