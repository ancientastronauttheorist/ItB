# Actual factory receiver through callback and first-null class return

The complete native factory now feeds its actual receiver and allocated sentinel
into the returned callback, both marker helpers, and the class helper's first
null-vector allocation. The callback/class phase runs continuously in one
Unicorn machine and stops at VA `0x006ec1bd`, before the callback resumes its
registry/table operations. The intervening closure invocation is an explicitly
supplied host boundary; the Lua VM is not executed.

Implementation:
[`native_lua_class_factory_callback_empty_class_conformance.py`](../src/observatory/native_lua_class_factory_callback_empty_class_conformance.py).
Independent logical model:
[`native_lua_class_factory_callback_empty_class_semantics.py`](../src/observatory/native_lua_class_factory_callback_empty_class_semantics.py).

## Finite producer and supplied host

The 54 cases combine the eighteen checked aligned factory profiles with vector
alignments 0, 7 and 31. Producer profiles vary name length 0, 16 and 255, both
caller profiles and three registry profiles. Name storage crosses a page edge;
the two name pointers remain distinct. The producer executes the complete
factory and initializer, including its native 24-byte record allocation and
closure publication. Its existing all-page, ordered-event, API-frame, register,
flag and Lua identity checks still run before the capture is accepted.

Actual receiver U=`0x0fffffcc` crosses a page boundary. U+52=`0x10000000` is
the embedded field containing P=`0x10000100`, the actual allocated record;
these identities are distinct. The producer initializes an empty destination
and a null vector. The host never substitutes a generated receiver or sentinel.

Named byte patches bind shared Lua import slots and literals, install the eight
host-frame bytes, and supply an empty source A=`0x14000000` with head
H=`0x14000100`. Source writes comprise A+52, the three head self-links and
head marker bytes 12 and 13. The source page was already mapped as unused
original factory userdata storage: these named bytes are explicitly reused.
All other bytes on that page remain preserved. Four new A5-filled construction
pages start at `0x06000000`; the successful allocation returns
V=`0x06002000` plus the selected alignment. The original producer U72 and P24
bytes are unchanged at the host boundary.

Class entry C is `0x30001000` or `0x3000100f`; callback entry T=C+48. This
frame reuses historical factory scratch. Current callback ancestors and its
local pair are preserved; historical scratch is not claimed to survive.
Only ESP changes from the native factory's returned register packet at the
host boundary. The returned closure must target `0x006ec110` with exactly U.
The cookie is read from the retained global at `0x00893f28`, yielding
`0x12345678` or `0xffffffff` for the two producer profiles.

## Continuous native boundary and return

The callback performs twelve supplied Lua requests and executes both native
marker bodies. Their identity-bound token interpreter preserves the single
original argument. The original local pair `[0,A]` is at T-20=C+28. Actual
class entry registers, return/argument words, all current data pages and defined
prefix ADD flags under `0xcd5` are checked before the class executes.

The class physical oracle begins with that prefix's current pages and registers;
generated child pages never replace running parent state. Empty source and
destination mean no insertion, successor traversal or key-string read. The
native growth, resize, allocation, retry, thunk, HeapAlloc wrapper, zero-length
copy and class cookie-return instructions execute. Heap import entry is T-188,
with `[return,handle,flags,bytes]=[0x00789463,0x12345678,0,8]`. All eight
request GPRs and defined TEST flags under `0xcc5` are checked. The successful
heap response remains an explicit supplied API contract.

The native class appends exactly `[0,A]`, sets U+4=V and U+8=U+12=V+8,
and executes RET4 to the suspended callback. The fifteen other userdata DWORDs,
all 24 sentinel bytes, source bytes, references, names, context, global/FS
pages and callback ancestors remain preserved. The class cookie frame is
T-52, with the stored cookie at T-56. At return:

| Register | Value |
|---|---|
| EAX, EDI | A |
| EBX | Lua state |
| ECX | Retained cookie |
| EDX | 0 |
| ESI | U |
| EBP | T-4 |
| ESP | T-40 |

Defined flags are `0x44` under mask `0xcd5`. This is the class helper's
normal return into a suspended callback, not the callback's normal return.
The independent logical model checks this packet, vector contents and field
updates. It validates strict words, the vector's disjointness from
U72/P24/original-frame spans, and the represented cookie cells;
it does not claim arbitrary mapped scratch.

## Coverage, controls and sealed evidence

There are 955 selected sites in 2,470 bytes. Exactly 261 sites execute:
67 callback/marker sites from the sealed entry proof and 194 independently
byte-pinned empty-class sites. The remaining 694 sites are explicitly excluded
from the normal sweep. Parent assertion/error arms, false-marker tails,
nonempty insertion/balancing/successor branches, allocation failures/retries,
free paths and the resumed callback suffix are outside this proof.
Every case executes 288 callback/class instructions; totals are 35,820 factory
instructions, 15,552 callback/class instructions, 1,836 factory Lua calls,
648 callback Lua calls, 54 factory and 54 class heap responses, and 108 native
marker calls. No tree insertions or frees occur.

All 22 controls reject for their exact declared reasons. They cover final
userdata, sentinel marker/padding, references, context, local pair, stale class
CALL word, ancestor, source, vector, capacity and global-cookie page changes;
final ECX and defined flags; wrong converted upvalue; both parent AL guards;
class-entry AF; and heap request, GPR, flag and response changes. The inherited
`receiver_register` control changes final ECX, which now holds the cookie.
The `cookie` control changes the global only after native return: it is a final
protected-page control, not a cookie-failure execution claim. Native failure
arms remain outside the sweep.

Receipt:
[`windows_build_13725832_31fe35265598_native_lua_class_factory_callback_empty_class_conformance.json`](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_empty_class_conformance.json).
Canonical SHA: `09117544ab5c8c4366aec36ee3bd295263157cdbd22455b1a1597d6eaf73851a`.
File SHA: `4352b1a18d11b76a4ec99ba46103886a647d1af48dfa6789001d5350ff215fc2`.
Deterministic UTF-8 LF size: 195,298 bytes. The CLI provides build, exact verify
and PE-free verify-structure. The shared entry engine's optional continuation
hooks preserve its original default sealed behavior.

Validation: 171 tests passed with no skips (75 independent model, 31 new
conformance, 38 unchanged entry and 27 aligned-producer tests). New build and
exact verify, PE-free structure verification, and the original entry rebuild
all passed. Independent semantic review: GO. All thirteen protected user-file
hashes remained unchanged before publication.

Real VM/metatable/registry effects, callback suffix and return, nonempty sources,
arbitrary receiver addresses, heap ownership, assertion delivery and global
decompilation accounting remain open. No accounting promotion is made.
