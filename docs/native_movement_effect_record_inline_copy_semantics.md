# Inline-string movement record copy semantics

`src/observatory/native_movement_effect_record_inline_copy_semantics.py` predicts
copying a mapped, disjoint 308-byte movement record with eight independent
inline strings of length zero through 15 and a path count zero through 511.
Its six keyword-only inputs retain the prior record-copy API. The complete
sixteen-field packet adds eight full fourteen-field string packets to the
prior fifteen-field record packet.

Each field copies its actual counted bytes, appends NUL and records its length
and inline capacity. Counted bytes may themselves contain NUL; source
terminators are not a premise. All 308 source bytes preserve. Exactly
`183 + sum(string lengths)` destination bytes are written; the remaining
`125 - sum(string lengths)` bytes preserve. Path capacity is unread. A zero
path needs no allocation runtime and may carry an unmapped empty begin pointer;
a positive path uses a supplied ordinary successful allocation of `8*N` bytes.

The owner carries actual returned EDX between fields, into the path child and
into the last string. Field child schemas, full scalar packets, actual inputs,
ordered prefix/suffix accesses, terminal ABI and complete checkpoint pages are
checked before adoption. Whole-record replay supports byte, word and DWORD
accesses. Validation rejects either selected string/CRT code page before any
writes or child calls. Reviewed canonical nested instruction metadata remains
trusted; tests explicitly accept valid transported instruction labels. This
is a stated trust boundary, not universal coordinated-forgery rejection.

For a path count N, the base trace/access/checkpoint counts are 492/315/20 at
zero or `571 + 10*N` / `364 + 4*N` / 23 at positive N. Each positive string of
length L, with q and r given by `divmod(L,4)`, adds
`38 + 6*q + 6*r + 2*(r!=0) + 2*(destination>source)` instructions,
`15 + 2*q + 2*r` accesses and two checkpoints. Full pages, GPRs, XMMs,
accesses, traces, defined flags, DF and endpoints are predicted.

Independent source review is GO. Seven mixed-length complete native probes
agree for null/unmapped empty paths and N=1,2,3,17,511. Seven all-empty cases
preserve the exact prior fifteen-field projection. The independent suite uses
handwritten parent/string/path expectations, separate final-byte equations,
strict schemas, EDX carry, full joins, rejection ledgers and declared metadata
trust. All 780 checks pass without skips in 106.78 seconds.

Heap strings, longer copies, growth, allocation failures, ownership, Lua
consumers, gameplay and broader native receipt sealing remain separate work.
Whole-program accounting is unchanged.
