# Short backward SIMD copy

This checkpoint covers rightward overlapping copy at RVA `0x0036e580` for
lengths 32–127, with source < destination < source+length. Bit one of the
stable feature DWORD at RVA `0x00493f30` must be set and entry DF clear.
Both exclusive buffer ends remain representable unsigned 32-bit words.
Mapped source/destination storage is separate from the protected stable
frame, code and feature word. MOVDQU/XMM architectural execution is assumed
available.

The path copies suffix bytes backward until the destination exclusive end is
16-byte aligned, then copies descending 32-byte blocks. Each block loads
both 16-byte halves before storing either half. A descending scalar tail
finishes the copy. No access exceeds the requested interval; all original
byte alignments are allowed. Destination receives an independent snapshot
of the original source and other payload bytes remain unchanged.

Let `h=(destination+length) mod 16` and `m=length-h`. When `m<32`, no SIMD
transfer occurs and all XMM registers preserve their entry values. Otherwise
XMM0 and XMM1 hold the final, lowest original 32-byte block halves, beginning
at source offset `m mod 32`; XMM2–7 remain unchanged. EAX returns destination,
ECX is zero, EDX remains original length, and other general registers restore.
Cdecl return advances entry ESP by four. CF/OF/SF are zero and PF/ZF are one;
AF is undefined when `m` is divisible by four, otherwise zero. DF stays clear.

## Evidence and limits

The semantic model covers all 61 admitted sites and 187 bytes in 1,824 cases.
Exact Unicorn 2.1.4 replay covers the same sites in 2,688 cases, including
alignment cases with no SIMD transfer. The pinned full function witness
contains 404 sites and 1,330 bytes. Independent reviewers approved both
bounded artifacts.

All XMM/general registers, defined flags, DF, ordered suffix/vector/scalar
accesses, complete payload and stack memory, and the feature word are checked.
For this emulator each architectural 16-byte MOVDQU transfer produces two
ordered 8-byte hooks; the oracle preserves architectural load/store ordering
while matching that instrumentation. Three semantic mutation controls and
separate replay payload/XMM corruption controls are rejected.

Forward copy, the 128-byte vector loop, larger lengths, other feature paths,
overread permissions and actual game execution remain excluded. This is a
bounded proof with explicit memory premises, not global accounting promotion.

## Reproduction

`scripts/itb_native_backward_simd_copy_semantics.py` takes `--program-facts`
and `--scalar-copy-semantics`; its conformance counterpart takes `--semantics`.
Both expose `build`, `verify` and `verify-structure`, with deterministic
UTF-8/LF JSON and binary stdout. Exact commands require `--executable`;
verification requires `--evidence`.

`tests/test_itb_native_short_simd_copy.py` covers both short SIMD directions,
and all 70 tests passed, including four exact CLI rebuilds. The exact checks
are enabled by `ITB_EXACT_EXE` and the private Unicorn runtime on `PYTHONPATH`.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_backward_simd_copy_semantics.json`: canonical
  `5e5fc334a1d99e6d920826c1f96b1c97693e9b041fc58c9453a9fc6d0e2849bd`;
  raw `1ffcfaf5eb034436c43983f9992b4af4502395d531eb8a2b00a38266e9c0d775`.
- `native_backward_simd_copy_conformance.json`: canonical
  `5fdeb35371c99740bacb1fed464a02bfc2df9eab7b82e1cfbd7144bf1fbfb225`;
  raw `70c89bf0685be4cc62ca4f21d0cbf433b0b982de5235b13bbc35ae46c2842bd8`.
