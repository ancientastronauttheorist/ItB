# General ordinary normal AddMove semantics

`src/observatory/native_movement_addmove_small_normal_semantics.py` predicts the
normal movement-record construction path for actual counts two through 511
and ordinary capacity from count through 511. Its six keyword-only inputs
retain the prior normal-law API; its complete fourteen-field output and
four-field path description retain exact count-two compatibility.
Independent source review is GO. All 393 independent checks pass without skips
in 233.96 seconds; five full-state executable cases agree.

The caller's begin, end and capacity determine used count N and capacity K.
The complete original `8*K` buffer is mapped and preserved, including spare
bytes. Three supplied disjoint allocation successes request `8*N` each within
the ordinary DATA region, excluding the error page. The receiver has existing
space for one 308-byte record; all eight selected strings are empty and inline.
Protected stack, header, record, complete capacity, runtime pages and all
lower two-page stack windows are checked before child calls.

Reviewed default construction, positive small assignment, small record copy,
small append and both small destructors compose around the unchanged owner
instructions. Allocations D1, D2 and D3 are followed by releases D2, D1 and
the original buffer. The original release uses capacity K. Its complete
eight-field primitive packet is manually predicted and compared before
transporting the checked RET event to the actual caller continuation.
SAR3 flags use `0xc5`, excluding undefined AF and OF.

The owner predicts `2029 + 30*N` instructions and `1269 + 12*N` accesses,
sixteen complete primary boundary states and six complete import states.
Final EAX is one, ECX the cookie, EDX the supplied free scratch result and ESP
entry plus twenty. Nonvolatile GPRs preserve. XMM0 holds the parameter's raw
bits; other XMMs preserve. The new type-four, mode-zero record contains the
complete copied path, and receiver end advances 308 bytes. Cookie comparison
leaves defined flags `0x44` under `0x8d5`; DF is zero.

Parent COMMON envelopes and top-level child key sets are typed; reviewed
extra and nested child metadata and instruction semantics remain trusted.
Independent tests explicitly accept valid trusted metadata changes alongside
rejecting COMMON forgeries, complete free-packet corruption and invalid
upfront geometry using pre-child ledgers. Handwritten parent and independently
handwritten child laws cover complete pages, ABI, accesses, traces, states,
ordinary flags, capacity-derived free, detachment and compatibility.

Executable cases N2/K2, N2/K511, N3/K17, N17/K511 and N511/K511 agree on all
complete boundary/import states, pages, GPRs, XMMs, accesses, traces, flags,
DF and endpoints. Growth, nonempty strings, aligned allocation, failure,
unwind, ownership, Lua consumers and gameplay remain separate work. No broader
native corpus seal or whole-program accounting promotion follows.
