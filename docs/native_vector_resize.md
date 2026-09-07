# Conditional vector resize owner

The owner at `0x002eb680` now has a complete 101-byte, 46-site conditional
protocol. Allocation, copy and deallocation return through explicit summaries;
the owner instructions themselves are modeled and replayed exactly.

It saves the requested count, calls allocation, reads the old begin and end,
and calls copy with the new pointer, old begin and modular byte length.
Copy is called even for zero bytes. The owner then rereads old begin and end,
computes the signed-shift element count, and calls deallocation only when
old begin is nonzero. That call receives old begin, the signed-shift capacity
count and stride eight. It publishes new capacity, new end and new begin in
that order, then restores its original frame.

For arbitrary 32-bit fields, copy length is u32(end-begin), while the published
end is new_pointer plus that length with its low three bits cleared, modulo
2^32. The signed arithmetic shift and subsequent multiplication yield this
identity even for high-bit displacements. Ordinary ordered, eight-byte vector
geometry is a separate checked domain. Its requested capacity must hold the
old live elements, and its new payload extent must not wrap. Those geometry
checks alone do not establish mapped storage or prove the copy's effect.

## Frames and explicit child premises

Let S be owner entry ESP. The allocation CALL enters at S-28 and its normal
RET 4 restores S-20. Copy and deallocation CALLs enter at S-36; their cdecl
returns and the owner's ADD 12 restore S-20. Final RET 4 leaves S+8.
The initial PUSH of the object pointer at S-8 is later overwritten by the
requested-count local; both writes are checked in the ordered memory trace.

All child summaries preserve every modeled frame and object word, including
pushed arguments, plus nonvolatile registers. Allocation supplies the chosen
new pointer. Volatile outputs are explicit fixed samples. Final EAX is new end;
EBX, ESI, EDI and EBP are restored. With null old begin, ECX is zero, EDX comes
from copy and flags come from TEST zero, excluding undefined AF. With nonnull
old begin, ECX/EDX come from deallocation and all six final flags come from
the owner's ADD ESP,12. Callee flags do not survive that ADD.

## Evidence

The graph receipt checks 432 cases across all 46 sites, with 1,168 supplied
child returns and four rejected semantic mutations. The separate Unicorn
2.1.4 receipt checks 1,600 cases across all sites, with 4,416 actual CALLs
into excluded boundaries. Hooks stop before synthetic stop bytes execute
and supply the declared responses. No child instruction or payload memory
access executes in this owner-only replay.

An independent oracle checks complete stack and object pages, ordered DWORD
reads and writes, all general registers and defined flags. It covers all
16 stack alignments, two object alignments, ordinary layouts and explicitly
synthetic wrap/sign/unaligned states. A wrong allocation response is rejected.
Independent semantic and replay reviews passed, as did all 34 focused tests,
including exact-executable CLI rebuilds.

Actual allocation, copy, free, failure behavior and changing metadata across
calls remain outside this contract. No complete resize equivalence or
whole-program accounting promotion is claimed.

## Reproduction

`scripts/itb_native_vector_resize_semantics.py` takes `--program-facts`,
`--allocation-semantics` and `--deallocation-semantics`; the conformance CLI
takes `--semantics`. Both provide `build`, `verify` and `verify-structure`.
Exact commands require `--executable`, verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_vector_resize_semantics.json`: canonical
  `b36551ea1b1f943b9f0d1b5802c9239a136feadc2c52443109d8e48669a89f89`;
  raw `633425972b153637bf9da41031d6db59d6c1fd2d033236238e9a817b30653856`.
- `native_vector_resize_conformance.json`: canonical
  `462fdaa9796d1c68ca53de46b0db4c38553486616e0f8314a240ef0546c1e13b`;
  raw `2f3012aa6240325e493a88762471c53f382b24b8f5bb5c8be72a301a79c15efd`.
