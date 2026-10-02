# General ordinary normal AddCharge semantics

`src/observatory/native_movement_addcharge_small_normal_semantics.py` predicts
the normal Charge wrapper around the general small-path AddMove law. Six
keyword-only inputs and the full fourteen-field packet retain prior count-two
compatibility. Independent source review is GO; all 411 distinct checks
validate. The initial gate passed 409 in 359.32 seconds; 36 affected geometry
and domain checks passed in 10.90 seconds after correcting two test fixtures.
The implementation required no correction. Five executable cases agree.

The selected geometry admits used counts two through 384 with ordinary caller
capacity from count through 511. Four disjoint `8*N` buffers fit in the proof
harness's 12 KiB usable DATA extent, reserving its error page. The 384 bound
belongs to this artifact layout; it is not a game limit. Broader synthetic
runtime layouts are separate work. Complete caller capacity bytes, receiver
record space, protected frames and lower two-page runtime windows are mapped
and disjoint before child calls. Selected strings are empty and inline.

The wrapper loads the raw parameter into XMM0, rewrites the fourth caller
argument to its stack path block, clones the original path and calls AddMove.
The successful inner result changes the newest record's mode to two. Supplied
allocations D0, D1, D2 and D3 are followed by releases D2, D1, D0 and the
original path. The outer release uses caller capacity K and closes the full
eight-field primitive packet before transporting only its checked RET event.
SAR3 uses mask `0xc5`, excluding undefined AF and OF.

Complete output contains `2223 + 40*N` instructions and `1394 + 16*N`
accesses, six complete primary states and eight complete import states,
including full nested state prefixes. Final EAX is one, ECX cookie XOR entry
frame-minus-four, EDX the supplied free scratch result and ESP entry plus
twenty. Nonvolatile GPRs and seven XMMs preserve; XMM0 holds the parameter
bits. Final ADD flags use `0x8d5`; DF is zero. Receiver end advances 308 bytes,
and the new type-four record contains the complete copied path and mode two.

Parent COMMON envelopes and top-level child key sets are typed. Reviewed
extra and nested metadata and instruction semantics remain trusted. Tests
explicitly document valid metadata transport, and independently check complete
free-packet forgeries, upfront domain ledgers, full ABI/pages/accesses/states,
ordinary flags, capacity-derived release, compatibility and detachment.

Executable cases N2/K2, N2/K511, N3/K17, N17/K511 and N384/K511 agree on all
complete primary/import states, GPRs, XMMs, pages, accesses, traces, flags,
DF and endpoints. Growth, nonempty strings, aligned allocation, failure,
unwind, ownership, Lua consumers and gameplay remain separate gates. No broader
native corpus seal or whole-program accounting promotion follows.
