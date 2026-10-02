# Actual-page movement record copy with an empty path

The selected record copy at RVA `0x15b9b0` now has a clean-room actual-page
law. It copies scalar fields, constructs eight empty inline strings and takes
the zero-count path reserve return. All **345 independent pure tests pass**
without skips and independent source review is GO. Two private native probes
also match the full law; a sealed finite native corpus remains a separate gate.

`apply` accepts immutable mapped pages, all eight GPRs and XMMs, an installed
return word and ordinary DF-clear flags. Source and destination are distinct
308-byte records. The source's eight strings have size zero, capacity fifteen
and a zero first byte; its three path words are zero. Initial destination bytes
and source scalar bits are arbitrary. Source, destination, protected stack,
FS word and cookie spans must be mapped, nonwrapping and disjoint. FS base zero
is an explicit premise. Crossing pages and disjoint records sharing pages are
supported.

Only **183 destination record bytes are written; 125 bytes preserve their
supplied values**. Scalar fields use their native widths, including separate
byte copies at offsets `0x30` and `0x31`. String byte zero, size and capacity
are initialized, and the empty path header is cleared. A 308-byte memcpy or
memset would overwrite padding incorrectly. All 308 source bytes and every
unrelated mapped byte preserve. Source string capacity and terminator are
domain premises, not native reads by the selected empty helper.

Eight calls execute the disjoint empty-string assignment. The path owner
`0x9a8e0` calls reserve `0x9ac40` with count zero. Reserve clears AL and returns
without allocation; the owner skips the scalar copy. The complete selected
composition has **492 instruction occurrences, 315 ordered architectural
accesses and twenty full helper entry/return snapshots**. Its deepest saved
slot is entry ESP minus 72. The model checks each complete eleven-field string
child against a separate handwritten prediction before incorporating it.

The result has fourteen fields: source address, destination address and record
bytes, source snapshot, full registers, XMMs, pages, accesses, defined flags,
mask, DF, endpoint, trace and boundaries. Final EAX is the destination, ECX is
the cached cookie XOR entry ESP minus four, EDX is source plus `0xf8`, and ESP
advances by eight. Nonvolatile GPRs and every XMM preserve. Defined flags are
`0x85` under mask `0x8d5`, DF zero. The last string passes its source using EAX
while EDX retains the previous string's address.

The normal return restores FS and the saved registers. It saves a cookie but
calls no normal cookie checker. Its unwind-state writes retain their actual
order and width; the final state slot is DWORD seven after an earlier full
DWORD-zero store. No unwind or failure-handler behavior is claimed.

Tests independently handwrite the owner, string and zero-path access/trace
laws, twenty complete boundaries and separate final record/stack equations.
Coverage includes 96 recipes, all 128 ordinary flag words, crossing pages,
signed and conservative limits, adjacency, strict types and domains, complete
child-packet corruptions and detached inputs/results/snapshots. Production
`apply`, constants and native observations do not supply expected output.

The two private actual-machine probes at alignments zero and fifteen matched
all registers, XMMs, full pages, access/trace order and all twenty boundaries.
They do not expand this pure checkpoint into a published native proof.
Nonempty paths or strings, aliasing, general assignment, allocation, ownership,
append/destruction, actual AddMove/AddCharge, gameplay and whole-game accounting
remain open. Four complete selected bodies total 1,226 bytes and 386 loaded
sites; only normalized source facts and clean-room code are published.
