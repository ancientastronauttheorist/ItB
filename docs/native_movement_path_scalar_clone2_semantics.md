# Actual-page two-entry scalar path copy

The law in `src/observatory/native_movement_path_scalar_clone2_semantics.py`
describes the selected RVA `0x8aba0` scalar loop for two eight-byte path
entries. Independent source review is GO. All **353 independent pure tests
pass**, without skips; native owner and allocator composition is a separate
checkpoint.

`apply` accepts immutable complete pages, all eight GPRs and XMMs, the actual
source and destination pointers, an installed logical return word and
ordinary DF-clear entry flags. The source and destination span sixteen
bytes each and cannot overlap each other or the protected caller/saved-stack
span. Page crossings and either disjoint buffer order are supported. Exact
types reject Boolean aliases, subclasses, mutable pages and extra fields.
Conservative exclusive ends cannot exceed `0xffffffff`.

The helper performs four ordered DWORD read/write pairs. Including saved
register and caller accesses, its trace has exactly 31 instructions and 14
architectural memory accesses. The memory-looking NOP operand causes no
architectural read. Only sixteen destination bytes and two saved stack
DWORDs change; every other supplied byte is preserved.

Final EAX is destination plus sixteen, ECX is the source's last DWORD, EDX
retains the source end, ESP advances by four, and nonvolatile GPRs and every
XMM retain their supplied values. Defined flags are `0x44` under mask
`0x8d5`, with DF zero. The ten-field result includes full pages, registers,
XMMs, flags, mask, DF, endpoint, source snapshot, ordered accesses and trace.

The return is a positive installed logical endpoint outside the helper's own
body and touched data spans. The actual parent continuation `0x0049a921`
is admitted. The pure law does not claim that arbitrary endpoint words are
mapped executable code or that a parent runs after RET.

Tests independently handwrite all accesses and trace sites and predict full
pages without production `apply`, constants or observations. Coverage includes
alignment, profiles, both buffer orders, all 128 ordinary flag combinations,
crossing pages, signed and conservative address limits, adjacency, typed
domains, exact caller words and detachment. An initially overbroad test
assertion was corrected to permit a legitimate source read when the source
starts at the destination's end; production behavior was unchanged.

This checkpoint does not prove allocation, arbitrary path lengths, overlapping
copies, SIMD paths, actual record copy/append/destruction, AddMove, AddCharge,
gameplay or ownership. The complete selected body has 43 bytes and SHA-256
`92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b`.
