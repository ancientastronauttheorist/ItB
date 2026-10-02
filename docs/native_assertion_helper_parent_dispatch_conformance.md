# Native assertion parent dispatch

The exact Windows executable now runs RVA379cc2 through both selected getter
bodies and stops at the CALL entry of the selected opaque child. Mode3 always
selects the DWORD read at VA008b7534 in RVA38e392. Only a zero first result
executes RVA38c89f and reads VA008b7318. Alternate entry RVA379b31 is selected
iff first==1 or first==0/second==1; otherwise the endpoint is RVA379550.
Neither endpoint instruction executes.

The standalone [logical contract](native_assertion_helper_parent_dispatch_semantics.md)
checks eight GPRs, the actual caller words, getter frames, precise argument
order, CMP/CD5 or TEST/CC5 defined flags, ordered scalar accesses with source
RVAs and every mapped data-page byte. With entry ESP=Q, normal entry ESP is
Q-28 with return VA00779cf5 and four arguments: condition, file, line and
original caller return. Alternate ESP is Q-24 with return VA00779d09 and the
first three arguments. Incoming flags preserve supplied DF0; undefined TEST
AF and unmasked EFLAGS bits are not promoted to a complete flags contract.

All three bodies run continuously in one Unicorn2.1.4 x86 machine, with no
getter API stub. The 2,352 vectors combine seven uint32 values per getter,
16 stack alignments and three opaque caller-word/flag profiles. They include
zero/max caller DWORDs and signed-overflow, auxiliary-carry and parity edges.
The result has 384 alternate and 1,968 normal calls, 2,352 first-getter and
336 second-getter calls. Four source receipts pin 141 instruction bytes and
54 loaded sites; 39 sites execute across 71,184 native instructions. Native
stores to the global page are rejected and both complete globals survive.

The 19 controls comprise 15 machine mutations and four event/path-record
mutations. They exercise mode and getter ABI, returns, arguments, ancestor
and saved-frame bytes, global/padding preservation, DF, ordered accesses and
instruction paths. Missing/extra reads and a restored global-write record
are mutations of the observed access list; they do not execute a native
global-store instruction. The path control similarly mutates the trace.
Every control rejects at its declared boundary rather than an incidental
exception.

The published receipt is
`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_parent_dispatch_conformance.json`.
Canonical SHA256 is
`88c1e3a7c73d276650c41cd5f356d7bc72c46c410e35ef84f50aac3ad0d3c5ed`;
file SHA256 is
`5f80732d1f6fc73cbf89f19a832a2eb44405335d3dbc76f52b6f46130d7e5a20`.
The deterministic UTF-8 LF artifact has 288,103 bytes. The CLI provides
`build`, executable `verify`, and source-pinned `verify-structure` commands.

Independent tests derive register/frame equations, literal paths and flags,
ordered event hashes and complete page writes without delegating those
expectations to the logical model. Sixteen actual specimens cover every
alignment, all three profiles and all seven getter values. Receipt, source,
schema and deterministic-encoding mutations are checked separately.
All 99 native conformance tests and 254 logical regressions pass without skips,
353 combined, including exact CLI rebuild, verification and structure
verification. Independent final source/test and published-receipt review is
GO. All 13 protected user hashes remain unchanged.

These are supplied synthetic runtime global values, not observed bootstrap
defaults. Other getter modes, setter/failure descendants, opaque child bodies,
parent cleanup/return, alternate trap, dialog/abort/unwind, CRT identity,
hardware execution and ownership remain excluded. Whole-program accounting
is unchanged. The next join continues the actual callback assertion prefix
into this dispatcher without replacing intermediate state.
