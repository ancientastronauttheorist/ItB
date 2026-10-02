# Native four-record class SIMD append

The class helper at RVA `0x002eb140` now has a bounded standalone replay
through existing-key tree transfer, full four-record growth to capacity six,
external record append and normal caller return. All 288 cases run the native
growth and resize instructions: allocate48, copy32 with the retained-feature
MOVDQU path, supply successful free of old32, then append8. Five records remain
live, with the final eight capacity bytes preserved.

This is an ingredient for the fifth factory callback. It does not establish
that actual callback, Lua VM behavior, heap ownership, new-key insertion,
arbitrary strings, failure-handler behavior or whole-program accounting.

## Exact joins and memory

The corpus combines48 existing-key tree fixtures with vector alignment0/7/31
and two nontrivial eight-register XMM profiles. Source and destination have
equal canonical key sets of zero through seven nodes. All1,008 transfers
update an existing node; no tree allocation occurs. Each case makes one
48-byte allocation and one old32 free request under supplied successful API
responses. Those responses explicitly preserve all eight XMM registers.

With class frame `F`, growth enters at `F-40`, resize at `F-60`, copy at
`F-96`, allocation import at `F-136` and free import at `F-128`. Growth
returns at the actual installed class continuation `0x006eb205`. The class
model independently reconstructs every field of the18-field child packet:
all buffers, ordered events, full GPRs, XMMs, flags/mask, clear DF, geometry,
allocation/free metadata and resize/copy entry registers. Exact types and
schemas reject extra fields and Boolean integer substitutes.

Native boundary checkpoints check the full GPR set. The four selected MOVDQU
sites alone permit the emulator's ordered two8-byte halves per16-byte
architectural access, within exact old32/new32 extents. XMM0/XMM1 become the
two copied record halves; XMM2 through XMM7 remain unchanged. Every mapped
byte is checked, including old32, source argument, tree links, key bytes,
padding, stack, feature/cookie bytes, fresh filler and spare8.

## Receipt and reproduction

The receipt
`windows_build_13725832_31fe35265598_native_lua_class_simd_vector_return_conformance.json`
has939 loaded sites/2,440 bytes and384 executed sites. Its288 cases include
1,440 resulting live records,1,008 existing-key updates,288 allocations and
288 frees. Twelve controls reject ancestor/source/payload/vector/iterator,
heap request/response/free pointer, old storage, XMM and spare corruption;
cookie mismatch stops at the exact first failure frontier. Accounting stays0.

The receipt is293,348 bytes, deterministic UTF-8 LF:

- Canonical SHA: `f0ffcae4eec8beab14a2a24a6b6ecdd736ed523c39ea681ead624e4a7b98008f`.
- File SHA: `b9219218daa5519c7d2b5cb546b9bccab3491afa72bdfd3d8926714731d32500`.

`scripts/itb_native_lua_class_simd_vector_return_conformance.py` supports
`build`, `verify` and `verify-structure`, requiring every source-pin path.
Native commands require the privately supplied exact `--executable`;
verification requires `--evidence`. Tests use serial isolated subprocesses
with `ITB_EXACT_EXE` and the private reviewed runtime `PYTHONPATH`.
No executable bytes or raw disassembly are published.

The focused gate passes130 tests without skips, including all288 pure cases,
full child corruption controls, eight isolated native boundary cases, all
twelve native controls and exact CLI build/verify/structure. A separate native
full-corpus replay also reproduces the unchanged receipt.
The unchanged growth/resize predecessor gate passes258 tests without skips,
388 combined with the class gate. Independent final source review is GO.

The next composition must retain an actual verified fourth callback's pages,
GPRs and all eight XMM registers, then invoke the fifth callback with its
independently bound source7/destination8 tree, old8/16/24/32, fresh48/spare8,
U13/P24, cookie, Lua requests and both normal returns. See the
[fifth-frontier plan](native_lua_class_factory_callback_fifth_frontier.md).
