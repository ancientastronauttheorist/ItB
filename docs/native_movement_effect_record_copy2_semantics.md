# Actual-page movement record copy with two path entries

The law in `src/observatory/native_movement_effect_record_copy2_semantics.py`
composes the selected normal record copier with eight empty inline strings
and a two-entry path. Independent source review is GO and all **377 independent
pure tests pass**, without skips, in82.92seconds. Native sealing is separate.

`apply` accepts complete immutable pages, all eight GPRs and XMMs, ordinary
DF-clear flags, an installed return word and a supplied allocation result.
Source and destination are complete disjoint 308-byte records. Eight source
strings have size zero, capacity fifteen and a NUL first byte. The path has
exactly sixteen source bytes; its capacity word is arbitrary and unread.
Both path buffers are disjoint from records, the protected frame and globals.
The return is excluded from both new path buffers as well as earlier spans.
The selected allocation domain and actual stack window come from the path law.

The complete fifteen-field result includes full pages, GPRs, XMMs, source and
record snapshots, 591 instructions, 372 ordered accesses, 23 helper boundary
states and the complete path packet. The eight empty-string packets are
separately compared in full before integration. The complete reviewed path
law is a trusted child: its internal allocator and scalar packets have their
own whole-packet comparisons, while the record parent checks a typed envelope
and geometry before adoption. The parent does not independently recompute
every nested path field or reject every coordinated child forgery.

The destination record writes 183 bytes and preserves125 padding bytes; all
308 source bytes remain intact. Its path header names the supplied allocation,
which receives sixteen bytes. Final EAX names the destination record, ECX is
the cached cookie XOR entry ESP minus four, EDX is source plus `0xf8`, and ESP
advances by eight. Nonvolatile GPRs and all XMMs preserve. Defined flags are
`0x85` under `0x8d5`, with DF zero. SEH and cached cookie restore normally;
no cookie checker, destructor, exception unwind or failure handler executes.

Independent tests handwrite the full record owner and generalized path law,
all accesses, traces, boundary states and separate final byte equations. They
cover alignment/profile recipes, all128 ordinary flag combinations, actual
caller continuation, page crossings, signed and high bounds, strict types,
new-buffer return exclusions, detachment and bounded child-envelope controls.
A scope test makes the trusted nested path-field transport explicit. Private
continuous native probes corroborate two geometries at591 instructions,
372accesses and23 boundaries, without creating a published native corpus.

This checkpoint does not establish nonempty strings, arbitrary path lengths,
allocation failure, old destination ownership, frees, append, receiver growth,
normal AddMove, AddCharge, Lua reachability or gameplay. Nine complete selected
bodies total1,500bytes; exact body and source pins are in the module. It changes
no earlier receipt or whole-game ownership accounting.
