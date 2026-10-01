# Actual factory output through complete callback normal return

The native factory's actual aligned receiver now reaches the returned callback's
normal return, including both native marker helpers, empty-source class mutation,
first-null vector growth and both filtered Lua table-transfer helpers. Every
callback and selected helper instruction runs continuously in one Unicorn machine.
The complete factory runs first and supplies its checked actual pages and closure
across an explicit host invocation boundary. Lua VM invocation is still supplied.

Implementation:
[`native_lua_class_factory_callback_return_conformance.py`](../src/observatory/native_lua_class_factory_callback_return_conformance.py).
Independent logical model:
[`native_lua_class_factory_callback_return_semantics.py`](../src/observatory/native_lua_class_factory_callback_return_semantics.py).
This extends the [first-null class return proof](native_lua_class_factory_callback_empty_class_conformance.md).

## Producer, source and native continuity

The 324 cases combine its 54 producer/vector profiles with six table-transfer
recipes: both empty; init/finalize; other/empty; empty/other; other-init-finalize
versus finalize-other-init; and init-other versus other-finalize. Each producer
is executed and validated natively. Its closure must target VA `0x006ec110` with
the actual U=`0x0fffffcc` as its sole userdata upvalue. P=`0x10000100` remains
the factory's actual allocated sentinel, stored at the distinct field U+52.

The source A=`0x14000000` and head H=`0x14000100` remain explicitly supplied
and empty. Named source-byte patches additionally set A's first DWORD to 0 or
`0xffffffff`, and offsets 32/40 to references `[23,29]` or `[123,129]`.
Those twelve bytes are added to the predecessor's head and object+52 patches.
All other source-page bytes are retained. Destination first word and references
at U+32/U+40 are derived from the captured producer; no supplied replacement
receiver values are written. U+24 retains its third actual factory reference.

Shared API/literal bindings, the eight host-frame bytes and four fresh
construction pages are the predecessor's explicit host premises. Callback T
is `0x30001030` or `0x3000103f`, class C=T-48, and its original pair `[0,A]`
remains at C+28. Host stack and named source storage reuse historical factory
bytes. Every unmentioned producer byte survives the host boundary; historical
scratch subsequently used by the callback/helpers is not claimed to survive.

Child fixture metadata describes the empty source/destination and fresh vector.
Generated child pages never replace producer or running-parent pages. Actual
class entry and return pages, GPRs and defined flags are checked against both
the composed physical oracle and detached logical caller/return packets. The
heap request checks all eight GPRs, the native T-188 frame, the exact eight-byte
request and defined TEST flags. The actual returned allocation pointer and
volatile response identities are checked at its native continuation.

## Identity-bound requests and final state

A separate runtime interpreter consumes the twelve physical prefix requests
and supplied typed responses. It binds marker tokens to U and A, preserves
the original argument, and compares its full before/after trace to the pure
prefix model. Actual converted EAX values are independently checked at both
native conversion continuations. The old continuous suffix interpreter tracks
four actual registry references and two iterator streams. Its opaque original
argument token is mapped to A before comparing with the independent normal
model; no replacement Lua argument identity is introduced.

`init` and `finalize` categories are skipped; `other` categories produce
assignment requests to the destination registry values. These are conditional
API requests, not asserted real table mutations. Immediately before returning
zero results, five values remain in the modeled Lua stack: original argument,
destination/source registry values for offset 32, then destination/source
values for offset 40. Host handling of that stack is not executed.

The class appends `[0,A]` to the successful eight-byte allocation V. Native
callback code then copies A's first word into U+0. Final fields are
U+0=source word, U+4=V and U+8=U+12=V+8. The fourteen other receiver DWORDs,
all 24 sentinel bytes, source bytes, names, references, context, global/FS
pages, current callback ancestors and original pair remain preserved.

At normal return, EAX=0, ECX is the captured cookie, and ESP=T+4.
Incoming EBX/ESI/EDI/EBP are restored exactly. EDX follows the explicitly
supplied final table-response law `0xb0000300 + N`, where N is the second
table helper's API count. Defined flags are `0x44` under `0xcd5`. Endpoint
VA `0x0400a000` is the supplied host return boundary. The independent model
checks strict words and mutually disjoint U72/P24/source72/vector8/original
callback-frame spans. These are modeled extents, not an arbitrary deeper
scratch-memory or heap-ownership guarantee.

The native six-recipe sweep uses 20–62 callback API responses. The pure model
accepts all category lists of at most three entries per transfer, including an
80-request all-other maximum. That broader logical domain is not a broader
native conformance claim.

## Exact evidence and rejection boundaries

The selected union is 1,062 sites in 2,746 unique bytes. Exactly 368 sites
execute: 76 normal callback, 194 empty-class/growth/checker, 27 normal marker
and 71 table sites. The successful cookie checker is shared between class and
callback; it is counted once in the selected-site partition. All 694 remaining
selected sites are excluded from the normal sweep. Nonempty tree operations,
parent assertion/error arms, false-marker tails, allocation failures and free
paths remain outside it.

Totals: 214,920 factory and 142,236 callback/helper instructions; 11,016 factory
and 12,096 callback Lua requests; 324 factory and 324 class allocations;
648 native marker and 648 native table-helper calls; 324 assignment requests.
There are no tree insertions or frees, and no opaque native instruction stubs.

All 25 corruption controls reject for exact declared reasons. They cover final
ancestor/local pair/receiver word/reference/literal/IAT/vector/capacity,
sentinel padding, actual factory reference, source padding and global-cookie
bytes; zero result, cookie register and AF; retained Lua prefix; heap request,
GPRs, flags and pointer identity; actual U/A conversion identities; both AL
guards; and class-entry AF. Final global-cookie-page corruption is distinct
from native failure execution.

The 26th control changes the cookie before the callback's native comparison.
It reaches RVA `0x003574d5` before the failure handler executes. The existing
native runner checks exact failure GPRs/defined flags, ordered prefix events,
all pages, Lua trace and heap/API counts. It does not claim handler delivery
or exception semantics.

Receipt:
[`windows_build_13725832_31fe35265598_native_lua_class_factory_callback_return_conformance.json`](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_return_conformance.json).
Canonical SHA: `6b0f0ced057240a366ccd5c9545d482feb2d7fbcd3af70aaa5186779c3ad885e`.
File SHA: `80c3c514d6ebe07d5dec4a25a900ffa30f6dc064a4822d6910c59a2ddd8035c7`.
Deterministic UTF-8 LF size: 293,817 bytes. All 21 source receipts are strictly
pinned. The CLI provides build, exact verify and PE-free structure verification.
The old native callback runner's optional fixture/hooks retain its original
default behavior and sealed spare/growth boundaries.

Validation: **274 passed, no skips** (156 independent model, 41 new
conformance and 77 existing spare/growth callback tests). New native build and
exact verify are byte-identical to the seal; both older callback receipts also
rebuild identically. PE-free structure checks pass. Independent semantic review:
**GO**. All thirteen protected user-file hashes remained unchanged.

Real VM/registry/table/metamethod effects, nonempty source trees, arbitrary
native pointer domains, heap ownership, assertion delivery and whole-program
accounting remain open. No accounting promotion is made.
