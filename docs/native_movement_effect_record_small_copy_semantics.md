# Small path record copy semantics

`src/observatory/native_movement_effect_record_small_copy_semantics.py` predicts
copying a 308-byte movement record with eight empty inline strings and an
actual path count zero through 511. Its six keyword-only inputs describe pages,
GPRs, XMMs, return address, ordinary flags and a supplied allocation result.
Independent source review is GO; all 881 independent checks pass without skips
in 246.96 seconds. Seven complete executable probes agree.

Source and destination records must be mapped, disjoint and nonwrapping.
Positive source and allocation buffers contain `8*N` bytes and obey the
ordinary small-clone runtime geometry. Count derives from path end minus begin;
path capacity is unread. Zero requires allocation result zero, needs neither
allocator DATA nor heap/IAT pages, and may carry an unmapped empty path pointer.
The conservative two-page stack window remains required for every count.

The complete fifteen-field owner packet includes all pages, ABI, ordered
accesses, trace, flags, DF, endpoint, source and destination bytes, snapshots,
boundary states and the full path packet. Zero executes 492 instructions and
315 accesses with twenty checkpoints; positive executes `571 + 10*N`
instructions and `364 + 4*N` accesses with twenty-three checkpoints and one
allocation. Exactly 183 destination bytes are written; 125 padding bytes and
all 308 source bytes preserve. The copied path header describes the newly
allocated exact-size buffer, whose complete contents match the source.

Child schemas, allocator/scalar envelopes, terminal ABI, snapshots, access
replay and complete checkpoint-prefix pages are closed before adoption.
Reviewed nested instruction metadata remains trusted; independent tests
explicitly accept a valid transported scalar trace change while rejecting
incorrect bytes, reads, writes, checkpoints and terminal state. Tests cover
all ordinary flags, count and alignment boundaries, arbitrary capacities,
strict input types, pre-child ledgers, detachment and broad disjoint geometry.

Executable probes cover null and unmapped empty paths, counts one, two,
three, seventeen and 511. Every complete boundary/import state, page, GPR,
XMM, ordered access, trace, flag, DF and endpoint agrees. The prior empty
record's fourteen common fields retain compatibility; count two retains the
prior complete fifteen-field packet. Nonempty strings, aligned allocation,
failures, ownership, Lua consumers, gameplay and broader native receipt sealing
remain separate work; whole-program accounting is unchanged.
