# Standalone AL-zero AddCharge semantics

`src/observatory/native_movement_addcharge_early_semantics.py` predicts the
actual-page AddCharge wrapper whose inner zero-or-one-entry AddMove returns
AL zero. Independent source review is GO; all 821 independent checks pass
without skips in 52.13 seconds. Four exact executable probes reproduce every
primary/import state, full pages, GPRs, XMMs, accesses, trace and defined flags.

The six keyword-only inputs are pages, GPRs, XMMs, installed return, ordinary
entry flags and one supplied allocation result. The actual caller path is a
null triple or an owned zero/one-entry path with capacity one through 511.
Null and owned-empty paths require allocation result zero. A one-entry path
supplies an ordinary successful eight-byte allocation in the declared region.
Owned calls supply successful frees, without asserting real allocator
ownership or unmapping. Typed immutable state, mapped disjoint nonwrapping
extents, runtime words and conservative nested stack windows are enforced.

The exact fourteen-field result includes geometry, path, full ABI/pages,
events, trace, primary boundaries, imports, child packets, flags, DF and
endpoint. Null runs execute 115 instructions, 74 accesses, four primary states
and no import. Owned-empty runs execute 155, 99, six and one. One-entry runs
execute 284, 177, six and three: allocate the clone, free the clone in inner
AddMove, then free the original capacity in the wrapper.

The wrapper always loads the raw parameter into XMM0 with zero upper bits;
other XMMs preserve. It also writes the local argument-block pointer into the
caller's fourth argument word. Inner AL zero skips both latest-record
instructions, so the receiver header and source capacity bytes preserve and
no movement record is created or adjusted. Final EAX is zero for null, one
after owned cleanup; ECX is the cached cookie XOR the wrapper frame. EDX is
zero for null or the supplied volatile free-response value for owned paths.
ESP advances twenty bytes and nonvolatile GPRs preserve.

The complete clone and early-Move packets are adopted behind closed typed
envelopes, exact joins and access/page consistency checks. Reviewed nested
instruction semantics remain trusted; arbitrary coordinated nested forgeries
are outside the claim. The outer free's complete eight fields are manually
predicted and compared before transporting only its checked final RET and
stop to the installed wrapper continuation. Imported TEST flags use `0x8c5`,
capacity SAR uses `0xc5`, ordinary arithmetic `0x8d5`, with explicit DF zero.
The actual inner cookie checker executes; no outer cookie-check call is added.

Independent expectations compose handwritten small-clone and early-Move
oracles with a separate outer free law. Tests cover all admitted flags across
three forms, capacities through 511, strict schemas/domains, complete child
forgeries, prechild call ledgers, detached packets and declared nested trust.
Normal record creation, count-two and larger wrapper arms, failures, unwind,
ownership, Lua and gameplay are separate gates. Whole-program accounting and
the finite native receipt domains remain unchanged.
