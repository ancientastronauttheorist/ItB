# Fixed SIMD vector growth

The normal growth wrapper at RVA `0x002eb620` now has a standalone exact
replay for a full four-record vector. It computes capacity six, calls the
native resize owner, allocates48, copies32 through the retained-feature
MOVDQU path, supplies successful free of the old32 buffer and returns with
four live records/capacity six. This is an ingredient for the fifth callback;
class append, Lua, factory composition, actual heap ownership, allocator
reuse, failure behavior and global accounting remain outside the claim.

## Parent and child boundaries

The growth wrapper ignores the incoming argument word and discards it with
RET4. The fixture uses the actual caller word1; pure tests check preservation
of several nontrivial DWORDs. The resize request6 comes from the vector header,
not that incoming argument. With growth entry `G`, resize enters at `G-20`,
copy at `G-56`, allocation import at `G-96` and free import at `G-88`.
Growth restores its parent registers and returns at `G+8`.

The child receives the actual installed continuation `0x006eb66e`. Its copy
entry has ECX32/EDXoldbegin, and the outer cleanup preserves the resize flags.
A separate source-backed memory law joins the sealed allocation, SIMD copy
and free oracles. Before growth cleanup, the join checks the complete child
stack, ordered events, buffers, registers, XMM state, flags, DF and endpoint.
Complete child metadata is also bound to independent parent equations.

The24 cases vary two nontrivial GPR/XMM profiles, vector alignment0/7/31 and
stack alignment0/1/7/15. New/old buffers are at `DATA+0x2000` and `DATA+0x3000`,
with vector beginnings at offsets0x800+a. All old/error/feature/cookie bytes,
new filler and spare16 bytes remain unchanged. Every mapped byte, heap/IAT
global and ordered native access is checked; API responses explicitly preserve
all eight XMM registers.

## Receipt and reproduction

Eleven source pins preserve the normal growth, native resize, allocation/free
and short-SIMD witnesses. The receipt has314 loaded sites/824 bytes and203
executed sites. Every normal growth site below failure RVA `0x002eb674`, every
owner instruction and the selected feature test/four MOVDQU sites execute.
There are24 allocation and24 free summaries,768 copied bytes,1,152 allocated
bytes and zero accounting promotions. Five controls reject for their intended
ancestor-stack, payload, XMM, allocation-request and free-pointer reasons.

`windows_build_13725832_31fe35265598_native_simd_vector_growth_conformance.json`
is61,206 bytes, UTF-8 LF:

- Canonical SHA: `605dbce02a72434228128b45fbf008f05448c12f618af876b1cc27c920527bfb`.
- File SHA: `44844eb0cb4bda761cf51064967b8a2f2b13f1fa2e44993e338458861613fd6a`.

The script `scripts/itb_native_simd_vector_growth_conformance.py` supports
`build`, `verify` and `verify-structure`, requiring all eleven source paths.
Native commands require `--executable`; verification requires `--evidence`.
Focused tests use isolated subprocesses when `ITB_EXACT_EXE` and the private
reviewed runtime `PYTHONPATH` are set. No executable/runtime is published.

Validation:121 growth tests plus137 standalone-resize regressions pass without
skips,258 combined. Both exact CLI builds and verifications reproduce their
unchanged sealed receipts. Tests reject all four child-metadata mutations,
extra keys, coordinated stack/event corruption and flag-mask corruption.
Independent draft/final code, receipt and frontier-plan reviews are GO.

Existing scalar growth and standalone SIMD resize receipts remain unchanged.
Next is the class append of the fifth [0,A] record, followed by the complete
fourth-capture-to-fifth factory callback with independently checked XMM/DF
state, retained tree nodes, old vectors and all normal returns.
