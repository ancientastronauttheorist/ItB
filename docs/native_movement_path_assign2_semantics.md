# Actual-page assignment into an empty movement path

The law in `src/observatory/native_movement_path_assign2_semantics.py`
describes the selected `0xc5bb0` normal assignment from two eight-byte entries
into an empty destination header. Independent source review is GO and all
**381 independent pure tests pass**, without skips, in13.96seconds.

`apply` accepts complete immutable pages, all eight GPRs and XMMs, ordinary
DF-clear flags, an installed return word and a supplied allocation result.
The destination header must be three zero DWORDs. The source header names
exactly sixteen bytes; its capacity word remains arbitrary, unread and
preserved. Header, payload and frame spans must be disjoint and nonwrapping.
The actual stack window is derived from ESP, with the existing four-page
allocation domain and exact heap interface premises. Strict schemas reject
mutable pages, aliases, subclasses and incomplete mappings.

The selected branch skips the old-allocation free arm and calls reserve,
ordinary allocation and scalar copy. The fifteen-field result includes all
pages and GPR/XMM state, 162 instructions, 90 ordered accesses, seven complete
boundary states, the imported allocation state and full child packets. The
complete seven-field allocator and ten-field scalar packets are separately
predicted and compared before integration. One supplied successful HeapAlloc
response requests sixteen bytes; no operating-system allocator executes.

Reserve is entered at ESP minus28, allocation at minus48, the imported frame
at minus96 and scalar copy at minus40. The boundary event prefixes are
0,17,26,53,61,70 and84, with imported prefix45. Four installed scalar words
are destination, destination, source header and destination; only the first
is read by the scalar helper. Reserve sets AL to one while retaining the
pointer-derived high EAX bits. The destination header ends with begin D and
end/capacity D plus16, and the sixteen payload bytes match the source.

Final EAX names the destination header, ECX is the source's last DWORD, EDX
is the source end and ESP advances by eight. Nonvolatile GPRs and every XMM
preserve. Defined flags come from ADD(entry ESP minus36,16), under mask
`0x8d5`; DF is zero. Every unrelated supplied byte is preserved and outputs
are detached. The actual AddMove continuation `0x006573a7` is admitted as an
installed endpoint; the following MOVSS does not execute in this law.

Independent tests handwrite the owner and lower laws, all15 fields, complete
child packets, boundaries and separate final stack/header/payload/page byte
equations. Coverage includes48 recipes, all128 flags, broader low/signed/top
geometries, unread capacity, typed domains, coordinated child corruption and
detachment. Four private actual native probes match162 instructions,90
accesses, all seven boundaries and the full imported/final state; these probes
do not create a published broader native corpus.

General path lengths, nonempty destination ownership, old frees, allocation
failure, aliases, growth, record append/destruction, ordinary AddMove,
AddCharge, Lua reachability and gameplay remain open. Seven complete selected
bodies total587bytes. Exact source and body pins are in the module; prior
receipts and whole-game accounting are unchanged.
