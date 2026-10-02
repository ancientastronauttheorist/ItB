# Disjoint scalar path copy for zero and positive counts

The actual-page law in `src/observatory/native_movement_path_scalar_semantics.py`
describes the selected `0x8aba0` scalar loop for zero or positive counts of
eight-byte records. Independent source review is GO; all339independent tests
pass without skips in9.06seconds. This extends the separately validated
count-two law without changing that law or its native corpus.

`apply` accepts complete immutable pages, all8GPRs and8XMMs, source and
destination, installed return and ordinary DF-clear entry flags. The source
end is incoming EDX; end-minus-source must be nonnegative and divisible by8.
Positive copies require positive disjoint mapped buffers and nonwrapping
conservative extents, outside the mapped protected caller frame and selected
code pages. The source and destination need not be mapped when the count is
zero, and may then be null or alias the frame as empty spans. Zero count
performs no source or destination storage access. Installed caller words must still match.

The complete ten-field output predicts source snapshot, full pages and
register/XMM state, ordered architectural accesses, dynamic canonical trace,
flags/DF and installed endpoint. Zero count executes10instructions and6stack
accesses. Positive count N executes11+10N instructions and6+4N accesses: one
nonzero-destination loop body per eight-byte entry, with two DWORD reads and
two DWORD writes. The loop preserves source bytes and every unrelated page.
No allocator, API response, SIMD transfer or native delegation is involved.

Final EAX is destination+8N; ECX is the last source DWORD for positive N and
incoming source for zero N. EDX preserves, ESP advances4, nonvolatile GPRs
and all8XMMs preserve. Final equal-end CMP flags are0x44 under0x8d5, with DF0.
The source/destination limits are conservative; wrapping, negative/misaligned
counts, overlap and positive null destination take other arms or are excluded.

Independent tests handwrite every output field and cover counts0/1/2/3/17/131/
513, all16alignments and128ordinary entry flag words, source/buffer/frame/return
adjacency and overlaps, page crossings, low/signed/high-end frames and exact
unsigned bounds, unmapped zero extents, typed schemas, caller unused words and
nested detachment. Seven private continuous executable probes match complete
pages/GPR/XMM/trace/events/flags for zero null, zero unmapped maximal source,
and counts1/2/3/17/131. Count2 matches the old law's entire ten-field packet.
Those probes are preliminary evidence; no published native corpus is created.

The complete selected body is43bytes with SHA-256
`92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b`.
Its21instruction sites have point anchor
`00e19fe1ff0f550f9d1a6687ad075fcc47ab42ecd1816df179f93850a4e0c1a6`.
General path allocation/clone/assignment, larger movement builders, positive
null-destination behavior, ownership and actual gameplay require separate
proofs. Whole-program accounting is unchanged.
