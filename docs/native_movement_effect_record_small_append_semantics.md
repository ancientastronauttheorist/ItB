# Small path record append semantics

`src/observatory/native_movement_effect_record_small_append_semantics.py` predicts
appending an external 308-byte movement record into existing receiver capacity.
Eight empty inline strings and actual path counts zero through 511 compose the
reviewed small record-copy law. Independent source review is GO; all 670
independent checks pass without skips in 251.58 seconds. Seven complete
executable probes agree, including prior count-two packet compatibility.

The receiver's begin, end and capacity must be record-aligned with space for
one record. Source and destination records are mapped, nonwrapping and disjoint;
the selected source address is at or above receiver end. Positive path buffers
are disjoint complete `8*N` extents with one supplied ordinary successful
allocation. Zero requires allocation result zero and no allocator runtime.
Protected stack, FS, cookie, record and runtime extents are checked upfront.
Growth, internal-source insertion, nonempty strings and aligned paths are
separate branches.

Each sixteen-field owner packet contains full ABI, pages, ordered accesses,
trace, flags, DF, endpoint, record bytes, source snapshot, receiver/source
addresses, complete boundary states and the complete nested record packet.
Zero executes 530 instructions and 344 accesses with twenty-two states;
positive executes `609 + 10*N` instructions and `393 + 4*N` accesses with
twenty-five states and one allocation. Receiver end advances by 308 bytes;
source bytes and all untouched mapped bytes preserve.

The nested fifteen-field record packet and its path, allocator and scalar
schemas are closed before adoption. A local replay supports byte, WORD and
DWORD accesses, checks reads against actual input bytes and restricts writes
to the child stack, FS, destination record and allocation buffer. Complete
terminal ABI and checkpoint-prefix pages agree with the replay. Reviewed
nested instruction and label metadata remains trusted, with explicit tests
of valid transported metadata changes; no universal coordinated-forgery claim
follows. Independent tests cover all ordinary flags, counts, geometry,
pre-child ledgers, exact schemas, page joins, detachment and preservation.

Executable probes at zero with null/unmapped pointers and counts one, two,
three, seventeen and 511 agree on every complete primary/import state, page,
GPR, XMM, access, trace, flag, DF and endpoint. The old count-two sixteen-field
packet remains exact. Broader native receipt sealing, ownership, failure,
unwind, Lua consumers and gameplay remain unfinished; whole-program accounting
is unchanged.
