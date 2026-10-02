# Default movement effect record: actual-page model

The constructor at RVA `0x001999a0` and its selected zero-length string path
now have a clean-room actual-page state model. It initializes a308-byte record,
seven helper calls and an eighth string inline, then returns normally.
Independent source review is GO and all302 focused pure tests pass without
skips in6.89seconds. Broader native conformance is a separate checkpoint.

## Domain and record preservation

`apply` takes actual immutable pages, all eight GPRs, all eight XMM registers,
an installed return address and ordinary incoming flags. It reads the caller's
arbitrary32-bit argument and initializes the record at entry ECX. It never
substitutes a fixture or executes native code. Exact types reject Boolean,
float, subclass and mutable-page aliases.

The record must lie above the selected empty source address `0x0080dfdc`.
Record, touched stack, FS word, cookie and literal spans must be mapped and
disjoint; record and stack may share a page when their touched spans do not
overlap. Arbitrary page crossings, signed-address boundaries and conservative
32-bit exclusive-end limits are admitted. Only ordinary flags under maskAD7
with fixed bit1 set are accepted, which also requires clear DF.

Eight inline string objects have offsets38/50/68/80/A4/E0/F8/118 hexadecimal.
Each receives a zero first byte, size0 and capacity15. The F8 object is
initialized inline; the other seven receive duplicate size/terminator stores
from the helper. The selected source/length/capacity branches execute no
allocator, copy, free or error child. The zero-length source is bound but
never dereferenced.

Defaults include argument at08, kind4 at0C, parameter0 atC8, empty path triple
atCC/D0/D4, mode0 atD8, value10 atDC and final3 at130. Sentinel and other
scalar defaults use their exact source widths. Only183 distinct record bytes
are written. The remaining125 bytes retain their supplied values; a whole
record memset would be incorrect. Complete mapped pages preserve outside
the documented record, stack and temporary FS stores.

## Caller and helper state

For constructor entry stack `S`, frame `F=S-4`, each helper enters at `S-40`
with `[continuation,0x0080dfdc,0]`. Its deepest saved slot is `S-56`; RET8
returns to `S-28`. The constructor restores FS, ESI and EBP, then RET4 reaches
`S+8`. Final EAX is the record, ECX is `cookie XOR F`, EDX and all nonvolatile
registers retain their incoming values, and all eight XMM registers preserve.

The constructor saves a cookie but has no normal cookie-check call. Its final
arithmetic instruction compares inline capacity15 with16, producing85 under
mask8D5. DF remains clear under the declared incoming premise. General string
behavior, cookie checking, unwind/failure handlers, ownership, record copying,
append, destruction, actual AddMove calls and gameplay remain open.

The returned13-field packet includes full record/pages/GPR/XMM,217 ordered
accesses,356 selected instruction occurrences, defined flags/DF/endpoint and
fourteen complete helper entry/return packets. Every result and boundary is
detached from the caller and from later mutations of other snapshots.

## Independent checks

The tests handwrite all default fields, exact padding, source trace and
accesses, full state and all fourteen boundaries. Production `apply`, its
constants and private observations do not supply expected outputs. Cases
cover48 base geometries, all128 ordinary flag words, arbitrary arguments,
page crossings, high unsigned addresses, adjacency and typed/schema/mapping
failures. Inputs remain unchanged. Source pins bind the exact program atlas
and the sealed movement binding; the logical domain does not expand any
finite native receipt or whole-game accounting.
