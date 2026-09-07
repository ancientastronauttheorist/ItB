# Short forward SIMD copy

This checkpoint covers the forward-safe MOVDQU branch of copy entry RVA
`0x0036e580` for lengths 32–127. Bit one of the stable feature DWORD at
RVA `0x00493f30` must be set, entry DF must be clear, and destination must
be at or below source or at or beyond the source exclusive end. Both buffer
ends must remain representable unsigned 32-bit words. The mapped buffers
are separate from the protected frame, code and feature storage. MOVDQU/XMM
architectural execution is assumed available.

Each 32-byte iteration loads both 16-byte source halves before storing either
half. A scalar tail handles the remainder. All byte alignments are permitted;
no read or write extends beyond the requested intervals. Destination equals
the original source snapshot, including safe leftward overlap, and other
payload bytes remain unchanged.

EAX returns destination, ECX is zero, and saved general registers restore;
cdecl return advances entry ESP by four. EDX is zero for a scalar remainder
below four bytes, otherwise it holds the last original source DWORD in that
tail. XMM0 and XMM1 contain the last original 32-byte block halves; XMM2–7
preserve their entry values. Final CF/OF/SF are zero and PF/ZF are one. AF is
undefined when the remainder is divisible by four, otherwise zero. DF stays
clear.

## Evidence and limits

The normalized semantic model covers 59 sites and 169 bytes in 2,688 cases.
The exact Unicorn 2.1.4 replay covers the same sites in 4,992 cases. The full
discontiguous function witness remains 404 sites and 1,330 bytes; this does
not establish equivalence for its other branches. Independent reviewers
approved both the model and replay.

Checks include all eight XMM registers, general registers, defined flags,
DF, ordered accesses, complete payload and stack memory, and the feature
word. Unicorn reports each architectural 16-byte transfer as two ordered
8-byte hooks. The independent replay oracle expands that transfer without
changing the two-load-before-two-store order. Three semantic mutation
controls and separate replay payload/XMM mutation controls are rejected.

The matrix covers every length in the semantic domain and all 16 byte
alignments at selected boundaries. Larger lengths, rightward overlapping
copy, other feature dispatch, aligned SIMD, overread permissions, actual game
execution and global accounting promotion remain outside this checkpoint.

## Reproduction

`scripts/itb_native_short_simd_copy_semantics.py` accepts `--program-facts`
and `--scalar-copy-semantics`; the conformance script accepts `--semantics`.
Both support `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`. JSON uses deterministic
UTF-8 and LF, including binary stdout on Windows.

The focused tests in `tests/test_itb_native_short_simd_copy.py` cover both
short SIMD directions. All 70 passed, including four exact CLI rebuilds.
Set `ITB_EXACT_EXE` to the pinned executable and
`PYTHONPATH` to `.local_decompile/fill_runtime` to enable the four exact CLI
rebuild checks. No executable or runtime is published.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_short_simd_copy_semantics.json`: canonical
  `ad1a4109a23a67bca5ae03b48dc3fe16cd2419000158a1d00f041c4fe488c17d`;
  raw `ec5b10bc557e3464c34393976b8215379f4c004ebd0b31d26a97999c052805a5`.
- `native_short_simd_copy_conformance.json`: canonical
  `67e3ceefdb4b00bfab28653b34634f51a1ab5310fd27b2f2e4bdd75324de5865`;
  raw `897e2824ca52788bd9814a8b6cee9319e2d9b67b222dd5374a30a5bb26d9bada`.
