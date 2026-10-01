# Fixed SIMD vector resize

The ordinary native owner at RVA `0x002eb680` now has a sealed standalone
replay for old size/capacity four and requested capacity six. It allocates48,
copies32 through the short forward MOVDQU path, supplies successful free of
the old32 buffer, and returns with four live records and capacity six.
Allocation/free responses are supplied API premises. This does not establish
the fifth factory callback, class append, Lua effects, actual heap ownership,
allocator reuse, failure behavior or global accounting.

## Composition and retained state

The fixture preserves feature word `0x93939393` and the complete feature/cookie
page. The24 cases vary two nontrivial GPR/XMM profiles, vector alignment0/7/31
and stack alignment0/1/7/15. Stack is at `0x30000000`, owner at `0x0fffffd0`,
new vector at `DATA+0x2800+a`, old vector at `DATA+0x3800+a` and error storage
in the separate `DATA` page.

At the copy entry, ESP is `S-36`, ECX32, EDXoldbegin, EAX/EDInewbegin,
ESIobject and EBP`S-4`. This boundary is checked against the pinned native
owner, whose SUB computes length in ECX. The independent copy join verifies
the full combined payload, full stack, all eight GPR/XMM registers, flags,
DF, endpoint and feature page before composing free and the owner suffix.

All old source bytes, error storage, filler and the16 spare new bytes remain
unchanged. Header writes occur capacity/end/begin; return advances ESP by8.
The native replay compares every mapped stack/buffer/object/feature/global/IAT
byte and every ordered memory access. Each16-byte architectural transfer is
observed as two ordered8-byte hooks; both source halves precede destination
stores. All eight XMM registers remain checked across supplied API responses.

## Evidence

Nine pinned predecessors provide the owner, allocation, free, small-copy,
small-resize and short-SIMD witnesses. Overlapping loader ranges must agree
on every point and byte. The receipt contains274 loaded sites/730 bytes,
165 executed sites,24 allocation and24 free summaries,768 copied bytes,
1,152 allocated bytes and zero accounting promotions. Coverage includes every
owner instruction and the selected feature test/four MOVDQU instructions.

Five mutation controls must fail for their intended ancestor-stack, payload,
XMM, allocation-request and free-pointer reasons. Tests also independently
check the buffer snapshot, header order, ABI/flags, spare storage, malformed
fixtures, source identities, component-packet corruption, receipt tampering
and exact CLI output. The105 focused tests pass without skips. Independent
draft and final receipt reviews are GO.
The existing allocation, scalar resize and growth regression gate also passes
102 tests, including unchanged native rebuilds:207 passing tests combined.

Receipt prefix: `windows_build_13725832_31fe35265598_`.
`native_simd_vector_resize_conformance.json` is53,994 bytes, UTF-8 LF:

- Canonical SHA: `553ca197fff9214a2dba573c44174d3407acc804dcda6b9cf73352a0964f05c7`.
- File SHA: `15a234c49c848d613e398f73b7c401e9706f8d1b7c871f8338169a77811f93ce`.

## Reproduction

`scripts/itb_native_simd_vector_resize_conformance.py` supports `build`,
`verify` and `verify-structure`. Every command requires all nine source paths;
native commands additionally require `--executable`, and verification requires
`--evidence`. Set `ITB_EXACT_EXE` and the private reviewed runtime `PYTHONPATH`
to enable isolated native tests and exact CLI gates in
`tests/test_itb_native_simd_vector_resize_conformance.py`.

Existing scalar resize/growth domains and receipts remain unchanged. Next
work is to connect the retained fourth factory callback to a fifth call,
carrying XMM/DF state and independently guarding that capture before binding.
