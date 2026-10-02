# Logical retained fifth callback

The pure model composes a fifth callback over the retained fourth logical
return. It takes exactly17 keyword-only inputs: the prior fourth packet's
inputs with its vector named `fourth_vector_pointer`, followed by the fifth
source, fresh vector pointer, entry and eight GPRs. It reconstructs all prior
packets and returns detached first-through-fifth results.

This is a logical conditional contract. It does not execute the factory,
callback, SIMD, Lua VM or heap, establish ownership, or promote accounting.
The [standalone native class proof](native_lua_class_simd_vector_return_conformance.md)
is an ingredient; an actual retained fifth factory callback remains open.

## Bounded inputs and results

Fifth incoming GPRs equal the independently reconstructed fourth full return,
except ESP is the supplied fifth entry. Source topology, keys, links and
colors equal fourth's seven-node source. Strict DWORD payloads may change or
remain equal. The retained eight-node destination keeps node identities and
the omitted key16 payload; all seven source keys route to existing nodes.
No fifth tree allocation is requested.

The shared operation and callback models have an explicit strict Boolean
`allow_fifth_growth` opt-in. It requires exactly four live records/capacity
four and computes capacity six. The callback also requires `allow_growth`.
All earlier default bounds and output schemas remain unchanged; the opt-in
rejects other full or spare geometries, including the next spare callback.

Growth requests48, copies32, frees old32 and appends the external [0,A] record
at offset32. Final size is5/capacity6; offsets40 through47 remain preserved
byte obligations. Retained first8, second16, third24 and fourth32 vectors are
disjoint from the complete new48 extent, U72, P24 and source72. Entry lies in
188 through0xfffffff8. Stack exclusion covers `[T-188,T+8)`, including the
allocation import, deepest growth frame and class cookie. Adjacent extents
are accepted; even one overlapping spare byte is rejected.

Independent source/destination routing, sentinel/count/payload laws, U13/P24,
Lua prefix/table/suffix request contracts, cookie, class return and full
return are checked separately from the composed model packets. The schema
does not carry XMM/DF; actual machine capture belongs to native conformance.

## Validation and next join

The203 new pure tests cover exact inputs, all GPRs, strict words, unchanged
payloads, retained IDs/key16, growth law/default bounds, aliases/spare bytes,
stack endpoints, adjacency, detached results and deliberately corrupted
prior/prefix/suffix packets. With fourth and shared operation/callback
regressions,586 tests pass without skips. Independent final source review is
GO. The actual four-callback predecessor's exact CLI build, verification and
structure gate reproduce its unchanged359,299-byte sealed receipt.

Next carry verified actual fourth pages, GPRs, eight XMM registers and flags
through an explicit fifth-only adapter. Preserve every old receipt and
reconstruct host patches byte-for-byte before executing the new callback.
The [frontier plan](native_lua_class_factory_callback_fifth_frontier.md)
defines the remaining216 producer cases and native failure controls.
