# Actual-page inline movement record destruction

The law in `src/observatory/native_movement_effect_record_destroy_semantics.py`
describes the selected `0x10e2a0` normal destructor for eight inline strings
and either a null path or two allocated path entries. Independent source
review is GO. All **501 independent checks are validated**, without skips:
500 passed in20.93seconds; one padding test changed a constrained null-path
triple, then both affected tests passed in2.81seconds after excluding those
premise bytes. Production behavior was unchanged by the test correction.

`apply` accepts complete immutable pages, all eight GPRs and XMMs, ordinary
DF-clear flags and an installed logical return word. Each inline string has
capacity15 and size at most15; its content bytes may vary. The path triple is
all zero, or begin O with end and capacity O plus16. The record, frame and
nonnull payload are disjoint and nonwrapping. Owned-path inputs additionally
supply complete actual stack/error pages and the exact synthetic heap interface.
Strict schemas exclude aliases, mutable pages and code-page mappings.

The null path executes80instructions and46accesses. It writes72record bytes
and preserves236. The nonnull path executes123instructions and74accesses,
including one count2/stride8 deallocation guard/free protocol. It writes84
record bytes and preserves224, and preserves the entire16-byte path payload.
Each inline string gets byte zero, size zero and capacity15. Nonnull path
headers clear; the null triple is preserved. No inline-string free executes.

The complete fifteen-field result predicts full pages, GPRs, XMMs, ordered
accesses and trace, record bytes, path pointer, two owned-path helper states,
the imported state and the complete free packet. The full eight-field generic
free packet is compared to a separate20-access, ABI, stack, error and protocol
law before rebinding only its canonical installed return and stop. One supplied
successful HeapFree response returns1 with explicit volatile GPR, flags and
stack effects while preserving all pages and XMMs. This does not free or unmap
actual operating-system memory or establish ownership.

The destructor saves ESI and EDI at entry ESP minus4 and minus8. The nonnull
free helper enters at minus24 and the imported frame at minus56, with words
`[0x00789172, 0x12345678, 0, O]`. Its imported prefix has39accesses. The free-entry
SAR has defined mask `0xc5`: OF is undefined for a multi-bit shift and was
removed from the initial draft's mask during independent review. Imported TEST
uses `0x8c5`; final CMP uses `0x8d5`. Raw native observations remain distinct.

Final EAX is15, ECX zero for a null path or `0xa0000001` after the supplied free,
EDX preserves for null or becomes `0xb0000001` after free, and ESP advances by
four. Nonvolatile registers and every XMM preserve. Final defined flags are
`0x85` under `0x8d5`, with DF zero. Outputs are detached. There is no SEH/cookie
prologue, failure handler, unwind or normal cookie-check call in this body.

Independent tests handwrite both complete paths, free/import states and packet,
all accesses and trace sites, and separate final page/record/payload/stack byte
equations. Coverage includes all128 flags, alignment/profile recipes, crossings,
low/high/signed bounds, adjacency, typed aliases, error/interface domains,
canonical return guards and detachment. Four private continuous native probes
match all states, full pages, traces, accesses and final raw `0x287`; no published
native corpus is created here. Five complete selected bodies total656bytes.

Non-inline strings, other counts/capacities, large-allocation metadata, free
failure, allocation, ownership, unmapping, exception unwind, normal AddMove,
AddCharge, Lua reachability and gameplay remain open. Earlier receipts and
whole-game accounting are unchanged.
