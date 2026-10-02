# Actual-page early AddMove semantics

`src/observatory/native_movement_addmove_early_semantics.py` predicts the
selected zero-or-one-entry AddMove arm from actual caller pages and state.
It constructs no finite fixture and performs no process-local native
delegation. Independent source review is GO. All 571 independent checks pass
without skips in 15.44 seconds, covering full handwritten packets, all admitted
flag combinations, capacities one through 511, broad geometry, complete free
packet forgeries, source preservation and detached state.

The five keyword-only inputs are pages, registers, XMMs, installed return and
ordinary entry flags. The actual caller words contain begin, end, capacity
and raw parameter bits. A null path requires an all-zero pointer triple;
an owned path has count zero or one and capacity one through 511 entries.
All capacity bytes are mapped, extents are nonwrapping and protected spans
are disjoint. The mapped two-page stack window is conservatively required
on both branches; owned calls require it disjoint from the entire error page,
matching the generic deallocator premise. Null calls require no heap, IAT or
error storage. Complete typed page, GPR and XMM schemas are enforced.

The fifteen-field packet contains path metadata, complete pages, eight GPRs
and eight XMMs, ordered accesses, trace, flags, mask, DF, endpoint, free entry,
free return, full free packet, import and cookie entry. Null calls execute
42 instructions and 25 accesses; owned calls execute 82 and 50. There is no
record construction, parameter MOVSS, allocation or receiver modification.
The parameter remains logical caller metadata and is never an architectural
read on this selected arm. All source capacity bytes and XMMs preserve.

Owned cleanup derives its free count from capacity minus begin, with stride
eight. The complete eight-field generic deallocation packet is independently
predicted and compared before transporting only its final canonical RET and
stop to the installed continuation. A successful ordinary HeapFree response
is supplied; page unmapping and real allocator ownership are outside the law.
Import TEST(begin) and cookie-entry TEST(cookie) use `0x8c5`, excluding undefined
AF. Capacity SAR uses `0xc5`, excluding undefined AF and OF. The actual cookie
comparison returns flags `0x44` under `0x8d5`, with explicit DF zero.

Final EAX is zero, ECX is the cookie, EDX is zero for null or the supplied
volatile free-response value for owned paths. ESP advances twenty bytes and
nonvolatile registers preserve. The receiver's twelve bytes, caller words,
source capacity storage and every untouched mapped byte preserve.

Six complete pinned bodies remain source witnesses. Root probes reproduce
all 144 established finite packets after correcting the imported TEST mask,
and four actual full-state cases cover capacity one, three and 511, null,
zero/high-bit cookies, signed pointers, high frames and the actual AddCharge
continuation. No broader native receipt or whole-program accounting promotion
is claimed. Count-two normal records, failures, unwind, Lua and gameplay are
separate gates.
