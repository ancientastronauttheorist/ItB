# Inline record destruction with small ordinary paths

`src/observatory/native_movement_effect_record_small_destroy_semantics.py`
generalizes the actual-page inline-record destructor to null paths or owned
capacity one through 511. Independent source review is GO and all 605
independent checks pass without skips in 9.54 seconds. Nine exact executable
probes agree at all observed states, including owned empty, partial and full
paths, capacity 511, crossing records and both null cases.

The five keyword-only inputs are actual pages, GPRs, XMMs, installed return
and ordinary entry flags. All eight strings must have inline capacity fifteen
and length zero through fifteen. An owned path's begin, end and capacity are
ordered and differ by whole eight-byte entries; used count may be zero through
capacity. Full capacity storage is mapped, disjoint and nonwrapping. The null
triple is all zero and needs no path buffer, heap/IAT or error page. Existing
typed page/state, frame, return, code and runtime guards remain in force.

The native owner reads capacity to derive the free count; it never reads the
path end word architecturally. Owned cleanup executes 123 instructions and
74 ordered accesses, including one supplied ordinary successful HeapFree
response. Null cleanup executes 80 and 46 with no import. The fifteen-field
result includes complete record bytes, full pages, GPR/XMM return, ordered
accesses, trace, boundary states, imported frame and the complete free packet.

The eight-field generic deallocation packet is manually predicted and compared
before transporting only its checked final RET and stop to the installed
continuation. Capacity SAR3 uses mask `0xc5`; imported TEST(begin) uses `0x8c5`.
The final inline comparison of fifteen with sixteen produces flags `0x85`
under `0x8d5`, with explicit DF zero. Final EAX is fifteen, ECX/EDX are the
supplied volatile free-response values for owned paths; null returns ECX zero
and preserves incoming EDX. ESP advances four bytes, nonvolatile GPRs and
all XMMs preserve.

Every inline string becomes empty with capacity fifteen. Owned paths have all
three header words cleared; all old capacity bytes preserve. Owned records
write 84 bytes and preserve 224 padding bytes; null records write 72 and
preserve 236. The old null and count-two/capacity-two complete packets remain
compatible. Full handwritten dynamic tests check every output field, unread
end, all ordinary flags, typed domains, pre-transport free forgeries and
detachment, with explicit prechild call ledgers.

Capacity 512 and larger need aligned metadata machinery. Non-inline strings,
failure, ownership, unmapping, exception unwind, Lua and gameplay remain open.
No broader native receipt or whole-program accounting promotion follows.
